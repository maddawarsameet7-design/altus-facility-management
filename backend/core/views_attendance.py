from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from .models import Attendance, Assignment, WorkerProfile
from .serializers import AttendanceSerializer
from .permissions import IsWorker, IsOpsUser, IsOwnerOrOps
from .mixins import SocietyScopedMixin, get_user_society_ids


class ClockInView(APIView):
    """
    POST /api/attendance/clock-in/
    Worker clocks in for a specific assignment.
    Body: { "assignment_id": "<uuid>", "lat": 18.52, "lng": 73.85 }
    Restricted to: WORKER only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not assignment_id:
            return Response(
                {"error": "assignment_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure the assignment belongs to this worker
        assignment = get_object_or_404(
            Assignment,
            id=assignment_id,
            worker__user=request.user
        )

        # Workers can only clock in to VERIFIED-worker assignments
        if assignment.worker.verification_status != 'VERIFIED':
            return Response(
                {"error": "Your account is not yet verified. Contact your supervisor."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Prevent duplicate clock-in
        if Attendance.objects.filter(assignment=assignment, clock_in__isnull=False).exists():
            return Response(
                {"error": "Already clocked in for this assignment."},
                status=status.HTTP_409_CONFLICT
            )

        attendance, _ = Attendance.objects.get_or_create(
            assignment=assignment,
            defaults={'society': assignment.request.society}
        )
        if not attendance.society_id and assignment.request.society_id:
            attendance.society = assignment.request.society
        attendance.clock_in = timezone.now()
        attendance.save()

        # Update live location if provided
        if lat is not None and lng is not None:
            try:
                worker = WorkerProfile.objects.get(user=request.user)
                worker.current_lat = float(lat)
                worker.current_lng = float(lng)
                worker.last_location_update = timezone.now()
                worker.save(update_fields=['current_lat', 'current_lng', 'last_location_update'])
            except WorkerProfile.DoesNotExist:
                pass

        # Advance assignment state
        if assignment.status == 'PENDING_ACCEPTANCE':
            assignment.status = 'ACCEPTED'
            assignment.save(update_fields=['status'])

        serializer = AttendanceSerializer(attendance)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ClockOutView(APIView):
    """
    POST /api/attendance/clock-out/
    Worker clocks out. Optionally attaches proof URL or photo upload.
    Body: { "assignment_id": "<uuid>", "proof_of_work_url": "...", "lat": ..., "lng": ... }
    Supports multipart/form-data for `photo_proof` file upload.
    Restricted to: WORKER only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def post(self, request):
        assignment_id = request.data.get('assignment_id')
        if not assignment_id:
            return Response(
                {"error": "assignment_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment = get_object_or_404(
            Assignment,
            id=assignment_id,
            worker__user=request.user
        )

        attendance = get_object_or_404(Attendance, assignment=assignment)

        if not attendance.clock_in:
            return Response(
                {"error": "Cannot clock out — no clock-in recorded for this assignment."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if attendance.clock_out:
            return Response(
                {"error": "Already clocked out for this assignment."},
                status=status.HTTP_409_CONFLICT
            )

        attendance.clock_out = timezone.now()

        proof_url = request.data.get('proof_of_work_url')
        if proof_url:
            attendance.proof_of_work_url = proof_url

        photo = request.FILES.get('photo_proof')
        if photo:
            attendance.photo_proof = photo

        attendance.save()

        # Mark assignment COMPLETED
        assignment.status = 'COMPLETED'
        assignment.save(update_fields=['status'])

        # Auto-resolve the service request if all workers are done
        service_request = assignment.request
        all_assignments = service_request.assignments.all()
        if all(a.status == 'COMPLETED' for a in all_assignments):
            if service_request.status != 'Resolved':
                service_request.status = 'Resolved'
                service_request.save(update_fields=['status'])

        serializer = AttendanceSerializer(attendance)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyAttendanceHistoryView(APIView):
    """
    GET /api/attendance/my-history/
    Returns the authenticated worker's own shift records, newest first.
    Restricted to: WORKER only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def get(self, request):
        worker = get_object_or_404(WorkerProfile, user=request.user)

        attendances = Attendance.objects.filter(
            assignment__worker=worker
        ).select_related('assignment__request__category').order_by('-clock_in')

        results = []
        for att in attendances:
            assignment = att.assignment
            req = assignment.request
            duration_hours = None
            if att.clock_in and att.clock_out:
                delta = att.clock_out - att.clock_in
                duration_hours = round(delta.total_seconds() / 3600, 2)

            results.append({
                "attendance_id": str(att.id),
                "assignment_id": str(assignment.id),
                "assignment_status": assignment.status,
                "service": req.category.name if req.category else None,
                "location": req.location,
                "clock_in": att.clock_in.isoformat() if att.clock_in else None,
                "clock_out": att.clock_out.isoformat() if att.clock_out else None,
                "duration_hours": duration_hours,
                "proof_of_work_url": att.proof_of_work_url,
                "has_photo_proof": bool(att.photo_proof),
            })

        return Response(results)


class WorkerLocationUpdateView(APIView):
    """
    PATCH /api/workers/location/
    REST fallback for workers to push GPS coordinates.
    The primary real-time path is the LocationConsumer WebSocket.
    Body: { "lat": 18.52, "lng": 73.85 }
    Restricted to: WORKER only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def patch(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if lat is None or lng is None:
            return Response(
                {"error": "Both lat and lng are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        worker = get_object_or_404(WorkerProfile, user=request.user)
        worker.current_lat = float(lat)
        worker.current_lng = float(lng)
        worker.last_location_update = timezone.now()
        worker.save(update_fields=['current_lat', 'current_lng', 'last_location_update'])

        return Response({
            "lat": worker.current_lat,
            "lng": worker.current_lng,
            "last_updated": worker.last_location_update.isoformat()
        })


class AttendanceViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    GET /api/attendance/        — List attendance records (scoped by role & society)
    GET /api/attendance/{id}/   — Detail view (own record for workers, any in society for ops)

    Access matrix:
      WORKER      → own records only (redirected to /my-history/ for richer output)
      SUPERVISOR  → records in supervisor's active societies
      DIRECTOR    → all records
      MEMBER/CHAIRMAN → 403
    """
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def get_permissions(self):
        """Members and Chairmen have no business calling this endpoint."""
        perms = super().get_permissions()
        role = getattr(self.request.user, 'role', '')
        if role in ('MEMBER', 'CHAIRMAN'):
            from rest_framework.permissions import BasePermission

            class Deny(BasePermission):
                message = "Members and Chairmen do not have access to attendance records."
                def has_permission(self, request, view):
                    return False

            return [Deny()]
        return perms

    def get_queryset(self):
        user = self.request.user
        role = user.role

        qs = Attendance.objects.select_related(
            'assignment__worker__user',
            'assignment__request__category',
            'society'
        )

        if role == 'WORKER':
            try:
                worker = WorkerProfile.objects.get(user=user)
                return qs.filter(assignment__worker=worker)
            except WorkerProfile.DoesNotExist:
                return qs.none()
        elif role == 'DIRECTOR':
            pass
        elif role == 'SUPERVISOR':
            society_ids = list(get_user_society_ids(user))
            qs = qs.filter(society__in=society_ids)
        else:
            return qs.none()

        assignment_id = self.request.query_params.get('assignment')
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)

        worker_id = self.request.query_params.get('worker')
        if worker_id:
            qs = qs.filter(assignment__worker_id=worker_id)

        return qs.order_by('-clock_in')

    def get_object(self):
        """Object-level: workers can only retrieve their own records; cross-society returns 404."""
        obj = super().get_object()
        user = self.request.user
        if user.role == 'WORKER':
            if obj.assignment.worker.user != user:
                from django.http import Http404
                raise Http404
        return obj
