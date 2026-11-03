import uuid
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import (
    User, ClientProfile, WorkerProfile, Property, 
    ServiceCategory, ServiceRequest, Assignment, 
    Review, ChatMessage, PaymentTransaction
)
from .serializers import (
    UserSerializer, ClientProfileSerializer, WorkerProfileSerializer, 
    PropertySerializer, ServiceCategorySerializer, ServiceRequestSerializer, 
    AssignmentSerializer, ReviewSerializer, ChatMessageSerializer, 
    PaymentTransactionSerializer, DeviceTokenSerializer
)
from .permissions import (
    IsClientUser, IsOpsUser, IsDirectorOnly,
    IsOwnerOrOps, IsWorkerSelf, IsOpsOrReadOnly
)
from .mixins import SocietyScopedMixin, get_user_society_ids
from .throttles import LoginIPThrottle


# ─── AUTH & USER ──────────────────────────────────────────────

class UserProfileView(APIView):
    """Returns the authenticated user's own profile (any role)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class RegisterView(APIView):
    """Public endpoint to register new users."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginIPThrottle]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email', '')
        password = request.data.get('password')
        role = request.data.get('role', 'MEMBER').upper()

        if not username or not password:
            return Response({"error": "Username and password required"}, status=status.HTTP_400_BAD_REQUEST)

        if len(password) < 6:
            return Response({"error": "Password must be at least 6 characters"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken"}, status=status.HTTP_409_CONFLICT)

        # Public registration only allows MEMBER or WORKER self-sign-up.
        # CHAIRMAN / SUPERVISOR / DIRECTOR must be created by a Director via admin.
        if role not in ('MEMBER', 'WORKER'):
            role = 'MEMBER'

        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        user.role = role
        user.save()

        if role == 'WORKER':
            WorkerProfile.objects.create(
                user=user, phone='', verification_status='PENDING'
            )

        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DeviceTokenView(APIView):
    """Register or update an FCM device token for push notifications (any authenticated role)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'web')
        
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        from .models import DeviceToken
        device_token, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'device_type': device_type
            }
        )
        
        return Response({"message": "Token registered successfully"}, status=status.HTTP_200_OK)


# ─── DASHBOARD & ANALYTICS ────────────────────────────────────

class DashboardStatsView(APIView):
    """
    Returns real-time platform statistics.
    DIRECTOR sees full platform stats.
    SUPERVISOR sees operational stats (no revenue).
    MEMBER/CHAIRMAN sees their own request summary.
    WORKER sees their own assignment/attendance summary.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = user.role
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)

        # ── Worker: personal stats ─────────────────────────────
        if role == 'WORKER':
            try:
                worker = WorkerProfile.objects.get(user=user)
                total_assignments = worker.assignments.count()
                completed = worker.assignments.filter(status='COMPLETED').count()
                return Response({
                    'role': role,
                    'total_assignments': total_assignments,
                    'completed_assignments': completed,
                    'pending_assignments': worker.assignments.filter(
                        status__in=['PENDING_ACCEPTANCE', 'ACCEPTED']
                    ).count(),
                    'average_rating': worker.average_rating,
                    'verification_status': worker.verification_status,
                })
            except WorkerProfile.DoesNotExist:
                return Response({'role': role, 'error': 'Worker profile not found'}, status=404)

        # ── Member / Chairman: their requests (scoped to their societies) ────
        if role in ('MEMBER', 'CHAIRMAN'):
            society_ids = list(get_user_society_ids(user))
            my_requests = ServiceRequest.objects.filter(reporter=user, society__in=society_ids)
            return Response({
                'role': role,
                'total_requests': my_requests.count(),
                'open_requests': my_requests.exclude(status='Resolved').count(),
                'resolved_requests': my_requests.filter(status='Resolved').count(),
                'total_paid': float(
                    PaymentTransaction.objects.filter(
                        request__reporter=user, request__society__in=society_ids, status='SUCCESS'
                    ).aggregate(t=Sum('amount'))['t'] or 0
                ),
            })

        # ── Supervisor / Director: full platform stats ─────────
        # Supervisors see only their societies; Directors see everything
        if role == 'SUPERVISOR':
            society_ids = list(get_user_society_ids(user))
            req_qs = ServiceRequest.objects.filter(society__in=society_ids)
            total_workers = WorkerProfile.objects.filter(assignments__request__society__in=society_ids).distinct().count()
            verified_workers = WorkerProfile.objects.filter(assignments__request__society__in=society_ids, verification_status='VERIFIED').distinct().count()
            pending_workers = 0
        else:
            req_qs = ServiceRequest.objects.all()
            total_workers = WorkerProfile.objects.count()
            verified_workers = WorkerProfile.objects.filter(verification_status='VERIFIED').count()
            pending_workers = WorkerProfile.objects.filter(verification_status='PENDING').count()

        total_requests = req_qs.count()
        open_requests = req_qs.exclude(status='Resolved').count()
        resolved_requests = req_qs.filter(status='Resolved').count()

        monthly_trend = []
        for i in range(5, -1, -1):
            month_start = (now - timezone.timedelta(days=30 * i)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            month_end = (now - timezone.timedelta(days=30 * (i - 1))).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ) if i > 0 else now
            count = req_qs.filter(
                created_at__gte=month_start, created_at__lt=month_end
            ).count()
            monthly_trend.append({'month': month_start.strftime('%b'), 'count': count})

        data = {
            'role': role,
            'total_requests': total_requests,
            'open_requests': open_requests,
            'resolved_requests': resolved_requests,
            'resolution_rate': round((resolved_requests / max(total_requests, 1)) * 100, 1),
            'total_workers': total_workers,
            'verified_workers': verified_workers,
            'pending_workers': pending_workers,
            'avg_rating': round(float(Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0), 1),
            'monthly_trend': monthly_trend,
        }

        # Revenue only visible to Directors
        if role == 'DIRECTOR':
            data['total_revenue'] = float(
                PaymentTransaction.objects.filter(status='SUCCESS')
                .aggregate(total=Sum('amount'))['total'] or 0
            )
            data['monthly_revenue'] = float(
                PaymentTransaction.objects.filter(
                    status='SUCCESS', created_at__gte=thirty_days_ago
                ).aggregate(total=Sum('amount'))['total'] or 0
            )
            categories = ServiceCategory.objects.annotate(
                request_count=Count('servicerequest'),
                revenue=Sum(
                    'servicerequest__transaction__amount',
                    filter=Q(servicerequest__transaction__status='SUCCESS')
                )
            ).values('name', 'request_count', 'revenue')
            data['categories'] = list(categories)

        return Response(data)


# ─── CORE VIEWSETS ────────────────────────────────────────────

class ClientProfileViewSet(viewsets.ModelViewSet):
    """
    Clients can only read/update their own profile.
    Supervisors and Directors can list/read all profiles.
    Only Directors can delete profiles.
    """
    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrOps]

    def get_queryset(self):
        user = self.request.user
        if user.role in ('SUPERVISOR', 'DIRECTOR'):
            return ClientProfile.objects.all()
        return ClientProfile.objects.filter(user=user)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can delete client profiles."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class WorkerViewSet(viewsets.ModelViewSet):
    """
    - WORKER: can read/update their own profile only.
    - SUPERVISOR: can list, read, assign. Cannot verify or delete.
    - DIRECTOR: full access including verify, reject, suspend, delete.
    """
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsWorkerSelf]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'WORKER':
            return WorkerProfile.objects.filter(user=user)
        if user.role == 'DIRECTOR':
            return WorkerProfile.objects.all()
        if user.role == 'SUPERVISOR':
            society_ids = list(get_user_society_ids(user))
            return WorkerProfile.objects.filter(
                Q(verification_status='VERIFIED') | Q(assignments__request__society__in=society_ids)
            ).distinct()
        # Members/Chairmen cannot list workers
        return WorkerProfile.objects.none()

    def create(self, request, *args, **kwargs):
        """Only Directors can create worker profiles manually."""
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can create worker profiles directly."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can delete worker profiles."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """List workers pending verification. Director only."""
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can view pending workers."},
                status=status.HTTP_403_FORBIDDEN
            )
        pending = WorkerProfile.objects.filter(verification_status='PENDING')
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Approve, reject, or suspend a worker. Director only."""
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can verify, reject, or suspend workers."},
                status=status.HTTP_403_FORBIDDEN
            )
        worker = self.get_object()
        action_type = request.data.get('action', 'approve')

        if action_type == 'approve':
            worker.verification_status = 'VERIFIED'
        elif action_type == 'reject':
            worker.verification_status = 'REJECTED'
        elif action_type == 'suspend':
            worker.verification_status = 'SUSPENDED'
        else:
            return Response(
                {"error": f"Invalid action '{action_type}'. Use: approve, reject, suspend"},
                status=status.HTTP_400_BAD_REQUEST
            )

        worker.save()
        return Response(self.get_serializer(worker).data)


class PropertyViewSet(viewsets.ModelViewSet):
    """
    Properties are managed by Clients (their own) and readable by Ops.
    Only Directors can delete properties.
    """
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ('SUPERVISOR', 'DIRECTOR'):
            return Property.objects.all()
        if user.role in ('MEMBER', 'CHAIRMAN'):
            # Return properties belonging to their client profile
            try:
                return Property.objects.filter(client__user=user)
            except Exception:
                return Property.objects.none()
        # Workers cannot browse properties
        return Property.objects.none()

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can delete properties."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class ServiceCategoryViewSet(viewsets.ModelViewSet):
    """
    Anyone (even unauthenticated) can read service categories.
    Only Directors can create, update, or delete categories and their pricing.
    """
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsDirectorOnly()]


class ServiceRequestViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    Society-scoped ServiceRequest viewset.
    - MEMBER / CHAIRMAN: create & view own requests within their society only.
    - WORKER: view only requests they are assigned to.
    - SUPERVISOR: view all requests in their societies, assign workers, update status.
    - DIRECTOR: full access across all societies.
    """
    serializer_class = ServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'  # used by SocietyScopedMixin

    def get_queryset(self):
        user = self.request.user
        role = user.role

        if role == 'DIRECTOR':
            return ServiceRequest.objects.all()

        if role == 'WORKER':
            return ServiceRequest.objects.filter(assignments__worker__user=user)

        # MEMBER / CHAIRMAN / SUPERVISOR — scoped to their societies
        society_ids = list(get_user_society_ids(user))
        qs = ServiceRequest.objects.filter(society__in=society_ids)

        # Members only see their own requests within the society
        if role in ('MEMBER', 'CHAIRMAN'):
            qs = qs.filter(reporter=user)

        return qs

    def perform_create(self, serializer):
        """Set reporter from auth, and society from the mixin's logic."""
        super().perform_create(serializer, reporter=self.request.user)

    def create(self, request, *args, **kwargs):
        """Only Clients (MEMBER/CHAIRMAN) can create service requests."""
        if request.user.role not in ('MEMBER', 'CHAIRMAN'):
            return Response(
                {"error": "Only Members or Chairmen can create service requests."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only Directors can delete service requests. Others get 404 if out-of-society, or 403."""
        self.get_object()
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can delete service requests."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update request status. Ops (SUPERVISOR/DIRECTOR) and assigned WORKER only."""
        srv_request = self.get_object()
        user = request.user

        if user.role == 'WORKER':
            # Workers can only mark In Progress or Resolved on their assigned requests
            if not srv_request.assignments.filter(worker__user=user).exists():
                return Response(
                    {"error": "You are not assigned to this request."},
                    status=status.HTTP_403_FORBIDDEN
                )
            allowed_statuses = ('In Progress', 'Resolved')
        elif user.role in ('SUPERVISOR', 'DIRECTOR'):
            allowed_statuses = dict(ServiceRequest.STATUS_CHOICES).keys()
        else:
            return Response(
                {"error": "You do not have permission to update request status."},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        if new_status not in allowed_statuses:
            return Response(
                {"error": f"Invalid or unpermitted status '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        srv_request.status = new_status
        srv_request.save()
        return Response({"status": srv_request.status})

    @action(detail=True, methods=['post'])
    def assign_worker(self, request, pk=None):
        """Assign a worker to a request. Ops only."""
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response(
                {"error": "Only Supervisors and Directors can assign workers."},
                status=status.HTTP_403_FORBIDDEN
            )
        srv_request = self.get_object()
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "worker_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        worker = get_object_or_404(WorkerProfile, id=worker_id)

        # Only assign verified workers
        if worker.verification_status != 'VERIFIED':
            return Response(
                {"error": f"Worker is not verified (status: {worker.verification_status})."},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment, created = Assignment.objects.get_or_create(
            request=srv_request,
            worker=worker
        )

        srv_request.status = 'Investigating'
        srv_request.save()

        return Response(AssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message on a request thread. Reporter, assigned worker, or ops."""
        srv_request = self.get_object()
        user = request.user

        # Check access: reporter, assigned worker, or ops
        is_reporter = srv_request.reporter == user
        is_assigned_worker = srv_request.assignments.filter(worker__user=user).exists()
        is_ops = user.role in ('SUPERVISOR', 'DIRECTOR')

        if not (is_reporter or is_assigned_worker or is_ops):
            return Response(
                {"error": "You are not a participant in this request."},
                status=status.HTTP_403_FORBIDDEN
            )

        content = request.data.get('content')
        if not content:
            return Response({"error": "Content required"}, status=status.HTTP_400_BAD_REQUEST)

        msg = ChatMessage.objects.create(
            request=srv_request,
            sender=user,
            content=content
        )
        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process payment for a request. Client (reporter) only."""
        srv_request = self.get_object()
        user = request.user

        if user.role not in ('MEMBER', 'CHAIRMAN'):
            return Response(
                {"error": "Only Members or Chairmen can initiate payment."},
                status=status.HTTP_403_FORBIDDEN
            )

        if srv_request.reporter != user:
            return Response(
                {"error": "You can only pay for your own requests."},
                status=status.HTTP_403_FORBIDDEN
            )

        if hasattr(srv_request, 'transaction') and srv_request.transaction is not None:
            return Response(
                {"error": "This request has already been paid"},
                status=status.HTTP_409_CONFLICT
            )

        amount = request.data.get('amount', srv_request.total_amount)
        if amount is None:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)

        tx_id = request.data.get('transaction_id', f"TX-{uuid.uuid4().hex[:8].upper()}")

        tx = PaymentTransaction.objects.create(
            request=srv_request,
            transaction_id=tx_id,
            amount=amount,
            status='SUCCESS'
        )

        srv_request.is_paid = True
        srv_request.save()

        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class ReviewViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    Society-scoped reviews — immutable audit trail.
    - MEMBER/CHAIRMAN: reviews on resolved requests in their society.
    - WORKER: reviews on requests they completed.
    - SUPERVISOR/DIRECTOR: read all in their scope.
    """
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'request__society'

    def get_queryset(self):
        user = self.request.user
        role = user.role

        if role == 'DIRECTOR':
            qs = Review.objects.all()
        elif role == 'WORKER':
            qs = Review.objects.filter(Q(reviewer=user) | Q(reviewee=user))
        else:
            society_ids = list(get_user_society_ids(user))
            qs = Review.objects.filter(
                Q(reviewer=user) | Q(reviewee=user),
                request__society__in=society_ids
            )

        request_id = self.request.query_params.get('request')
        if request_id:
            qs = qs.filter(request_id=request_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

    def create(self, request, *args, **kwargs):
        """Validate that the reviewer is a participant in the resolved request."""
        user = request.user
        request_id = request.data.get('request')

        if user.role != 'DIRECTOR':
            society_ids = get_user_society_ids(user)
            if user.role == 'WORKER':
                srv_request = get_object_or_404(
                    ServiceRequest, id=request_id, assignments__worker__user=user
                )
            else:
                srv_request = get_object_or_404(
                    ServiceRequest, id=request_id, society__in=society_ids
                )
        else:
            srv_request = get_object_or_404(ServiceRequest, id=request_id)

        if srv_request.status != 'Resolved':
            return Response(
                {"error": "Reviews can only be left for resolved requests."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_reporter = srv_request.reporter == user
        is_assigned_worker = srv_request.assignments.filter(worker__user=user).exists()

        if not (is_reporter or is_assigned_worker or user.role in ('SUPERVISOR', 'DIRECTOR')):
            return Response(
                {"error": "You are not a participant in this request."},
                status=status.HTTP_403_FORBIDDEN
            )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return Response({"error": "Reviews cannot be modified."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response({"error": "Reviews cannot be modified."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Reviews cannot be deleted."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class ChatMessageViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    Society-scoped chat messages. Only participants can read/write. No deletes.
    """
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'request__society'

    def perform_create(self, serializer):
        request_obj = serializer.validated_data.get('request')
        user = self.request.user
        if user.role != 'DIRECTOR':
            society_ids = [str(s) for s in get_user_society_ids(user)]
            if str(request_obj.society_id) not in society_ids:
                from django.http import Http404
                raise Http404
            is_reporter = request_obj.reporter == user
            is_assigned_worker = request_obj.assignments.filter(worker__user=user).exists()
            is_ops = user.role in ('SUPERVISOR', 'DIRECTOR')
            if not (is_reporter or is_assigned_worker or is_ops):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You are not a participant in this request.")
        serializer.save(sender=user)

    def get_queryset(self):
        user = self.request.user
        role = user.role
        req_id = self.request.query_params.get('request')

        if role == 'DIRECTOR':
            qs = ChatMessage.objects.all()
        elif role == 'WORKER':
            qs = ChatMessage.objects.filter(request__assignments__worker__user=user)
        else:
            society_ids = list(get_user_society_ids(user))
            if role in ('MEMBER', 'CHAIRMAN'):
                qs = ChatMessage.objects.filter(
                    request__reporter=user, request__society__in=society_ids
                )
            else:  # SUPERVISOR
                qs = ChatMessage.objects.filter(request__society__in=society_ids)

        if req_id:
            qs = qs.filter(request_id=req_id)

        return qs.distinct()

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Chat messages cannot be deleted."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
