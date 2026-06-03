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
    PaymentTransactionSerializer
)


# ─── AUTH & USER ──────────────────────────────────────────────

class UserProfileView(APIView):
    """Returns the authenticated user's profile including their role."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class RegisterView(APIView):
    """Public endpoint to register new users."""
    permission_classes = [permissions.AllowAny]

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

        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        if role not in valid_roles:
            role = 'MEMBER'

        # create_user only handles username, email, password natively
        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        user.role = role
        user.save()

        # Auto-create profiles based on role
        if role == 'WORKER':
            WorkerProfile.objects.create(
                user=user, phone='', verification_status='PENDING'
            )

        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ─── DASHBOARD & ANALYTICS ────────────────────────────────────

class DashboardStatsView(APIView):
    """Returns real-time statistics for dashboards."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)

        total_requests = ServiceRequest.objects.count()
        open_requests = ServiceRequest.objects.exclude(status='Resolved').count()
        resolved_requests = ServiceRequest.objects.filter(status='Resolved').count()

        total_workers = WorkerProfile.objects.count()
        verified_workers = WorkerProfile.objects.filter(verification_status='VERIFIED').count()
        pending_workers = WorkerProfile.objects.filter(verification_status='PENDING').count()

        total_revenue = PaymentTransaction.objects.filter(
            status='SUCCESS'
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_revenue = PaymentTransaction.objects.filter(
            status='SUCCESS', created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('amount'))['total'] or 0

        avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg'] or 0

        # Category breakdown
        categories = ServiceCategory.objects.annotate(
            request_count=Count('servicerequest'),
            revenue=Sum(
                'servicerequest__transaction__amount',
                filter=Q(servicerequest__transaction__status='SUCCESS')
            )
        ).values('name', 'request_count', 'revenue')

        # Monthly request trend (last 6 months)
        monthly_trend = []
        for i in range(5, -1, -1):
            month_start = (now - timezone.timedelta(days=30 * i)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if i > 0:
                month_end = (now - timezone.timedelta(days=30 * (i - 1))).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                month_end = now
            count = ServiceRequest.objects.filter(
                created_at__gte=month_start, created_at__lt=month_end
            ).count()
            monthly_trend.append({
                'month': month_start.strftime('%b'),
                'count': count
            })

        return Response({
            'total_requests': total_requests,
            'open_requests': open_requests,
            'resolved_requests': resolved_requests,
            'resolution_rate': round((resolved_requests / max(total_requests, 1)) * 100, 1),
            'total_workers': total_workers,
            'verified_workers': verified_workers,
            'pending_workers': pending_workers,
            'total_revenue': float(total_revenue),
            'monthly_revenue': float(monthly_revenue),
            'avg_rating': round(float(avg_rating), 1),
            'categories': list(categories),
            'monthly_trend': monthly_trend,
        })


# ─── CORE VIEWSETS ────────────────────────────────────────────

class ClientProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPERVISOR', 'DIRECTOR']:
            return ClientProfile.objects.all()
        return ClientProfile.objects.filter(user=user)

class WorkerViewSet(viewsets.ModelViewSet):
    queryset = WorkerProfile.objects.all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """List workers pending verification."""
        pending = WorkerProfile.objects.filter(verification_status='PENDING')
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Approve or reject a worker."""
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
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Property.objects.all()

class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]


class ServiceRequestViewSet(viewsets.ModelViewSet):
    """
    Unified API for Facility Management Requests.
    Supports Members (Creation), Workers (Status Updates), and Supervisors (Assignment).
    """
    serializer_class = ServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['MEMBER', 'CHAIRMAN']:
            return ServiceRequest.objects.filter(reporter=user)
        elif user.role == 'WORKER':
            return ServiceRequest.objects.filter(assignments__worker__user=user)
        return ServiceRequest.objects.all() # Supervisors & Directors see all

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        srv_request = self.get_object()
        new_status = request.data.get('status')
        valid_statuses = dict(ServiceRequest.STATUS_CHOICES)
        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid status '{new_status}'. Valid: {list(valid_statuses.keys())}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        srv_request.status = new_status
        srv_request.save()
        return Response({"status": srv_request.status})

    @action(detail=True, methods=['post'])
    def assign_worker(self, request, pk=None):
        srv_request = self.get_object()
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "worker_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        worker = get_object_or_404(WorkerProfile, id=worker_id)
        
        assignment, created = Assignment.objects.get_or_create(
            request=srv_request,
            worker=worker
        )
        
        srv_request.status = 'Investigating'
        srv_request.save()
        
        return Response(AssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        srv_request = self.get_object()
        content = request.data.get('content')
        if not content:
            return Response({"error": "Content required"}, status=status.HTTP_400_BAD_REQUEST)
        
        msg = ChatMessage.objects.create(
            request=srv_request,
            sender=request.user,
            content=content
        )
        return Response(ChatMessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        srv_request = self.get_object()
        
        # Guard against duplicate payments (PaymentTransaction has OneToOne to ServiceRequest)
        if hasattr(srv_request, 'transaction') and srv_request.transaction is not None:
            return Response(
                {"error": "This request has already been paid"},
                status=status.HTTP_409_CONFLICT
            )
        
        amount = request.data.get('amount', srv_request.total_amount)
        if amount is None:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        tx_id = request.data.get('transaction_id', f"TX-{uuid.uuid4().hex[:8].upper()}")
        
        # Create transaction record
        tx = PaymentTransaction.objects.create(
            request=srv_request,
            transaction_id=tx_id,
            amount=amount,
            status='SUCCESS'
        )
        
        # Update request status
        srv_request.is_paid = True
        srv_request.save()
        
        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

    def get_queryset(self):
        user = self.request.user
        qs = Review.objects.filter(Q(reviewer=user) | Q(reviewee=user))
        
        # Allow filtering by request ID
        request_id = self.request.query_params.get('request')
        if request_id:
            qs = qs.filter(request_id=request_id)
        return qs

class ChatMessageViewSet(viewsets.ModelViewSet):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ChatMessage.objects.all()
        req_id = self.request.query_params.get('request')
        if req_id:
            qs = qs.filter(request_id=req_id)
        return qs
