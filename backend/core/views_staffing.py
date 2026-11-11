import io
import os
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from PIL import Image

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import Http404, FileResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from .models import (
    Post, Shift, RosterAssignment, DailyRoster, LeaveRecord,
    AttendanceEvent, Alert, AuditLog, WorkerProfile, Site, Society,
    Membership, ReplacementRequest, ReplacementOffer, Notification
)
from .mixins import SocietyScopedMixin, get_user_society_ids
from .permissions import IsWorker, IsOpsUser, IsDirectorOnly
from .staffing_utils import is_within_geofence, rank_replacement_candidates, check_worker_hard_blocks
from .serializers_staffing import (
    PostSerializer, ShiftSerializer, RosterAssignmentSerializer,
    DailyRosterSerializer, LeaveRecordSerializer, AttendanceEventSerializer,
    AlertSerializer, AuditLogSerializer, ReplacementRequestSerializer,
    ReplacementOfferSerializer, NotificationSerializer
)


class RosterClockInView(APIView):
    """
    POST /api/roster/clock-in/
    Roster-based worker clock-in with GPS geofence, accuracy, selfie, and timestamp validation.
    Restricted to: VERIFIED workers only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'clock_in'

    def post(self, request):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if worker.verification_status != 'VERIFIED':
            return Response(
                {"error": "Your account is not yet verified. Contact your supervisor."},
                status=status.HTTP_403_FORBIDDEN
            )

        clock_in_uuid_str = request.data.get('clock_in_uuid')
        if not clock_in_uuid_str:
            return Response({"error": "clock_in_uuid is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            clock_in_uuid = uuid.UUID(str(clock_in_uuid_str))
        except ValueError:
            return Response({"error": "Invalid clock_in_uuid format."}, status=status.HTTP_400_BAD_REQUEST)

        # ── Idempotency Check (Scoped to this worker) ──
        existing = AttendanceEvent.objects.filter(worker=worker, clock_in_uuid=clock_in_uuid).first()
        if existing:
            serializer = AttendanceEventSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # ── Resolve Target DailyRoster Slot ──
        now = timezone.now()
        roster_entry_id = request.data.get('roster_entry_id')

        if roster_entry_id:
            try:
                slot = DailyRoster.objects.select_related('post__site', 'society__settings', 'shift').get(id=roster_entry_id)
            except DailyRoster.DoesNotExist:
                return Response({"error": "Roster slot not found."}, status=status.HTTP_404_NOT_FOUND)

            # Amendment 1: Once a slot is COVERED, the original worker's clock-in returns 409
            if slot.status == 'COVERED':
                if slot.covered_by_id == worker.id:
                    pass  # Replacement worker is allowed
                elif slot.worker_id == worker.id:
                    return Response(
                        {"error": "This slot has been reassigned to a replacement worker."},
                        status=status.HTTP_409_CONFLICT
                    )
                else:
                    return Response({"error": "You are not assigned to this roster slot."}, status=status.HTTP_403_FORBIDDEN)
            else:
                if slot.worker_id != worker.id and slot.covered_by_id != worker.id:
                    return Response({"error": "You are not assigned to this roster slot."}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Deterministic slot resolution for the current time window
            # Window: [shift_start_at - early_window, shift_end_at]
            from django.db.models import Q
            eligible_slots = DailyRoster.objects.filter(
                (Q(worker=worker) & ~Q(status='COVERED')) | Q(covered_by=worker),
                date__gte=now.date() - timedelta(days=1),
                date__lte=now.date() + timedelta(days=1)
            ).select_related('post__site', 'society__settings', 'shift')

            matched = []
            for s in eligible_slots:
                early_mins = getattr(s.society.settings, 'early_clock_in_minutes', 30) if hasattr(s.society, 'settings') else 30
                window_start = s.shift_start_at - timedelta(minutes=early_mins)
                window_end = s.shift_end_at
                if window_start <= now <= window_end:
                    matched.append(s)

            if not matched:
                return Response(
                    {"error": "No scheduled roster slot found for this shift window."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Exclude slots that already have completed attendance
            unclocked = [s for s in matched if not hasattr(s, 'attendance_event') or s.attendance_event.clock_out_at is None]
            if not unclocked:
                return Response({"error": "All scheduled shifts in this window are already completed."}, status=status.HTTP_400_BAD_REQUEST)

            # Pick slot with closest shift_start_at to current time
            slot = min(unclocked, key=lambda s: abs((s.shift_start_at - now).total_seconds()))

        # Check if slot already has an attendance event (1 event per slot enforced)
        if hasattr(slot, 'attendance_event'):
            existing_event = slot.attendance_event
            if existing_event.clock_in_uuid == clock_in_uuid and existing_event.worker == worker:
                return Response(AttendanceEventSerializer(existing_event).data, status=status.HTTP_200_OK)
            return Response(
                {"error": "This roster slot already has an attendance record."},
                status=status.HTTP_409_CONFLICT
            )

        site = slot.post.site
        settings_obj = getattr(slot.society, 'settings', None)

        # ── GPS Geofence & Accuracy Validation ──
        lat = request.data.get('lat') if request.data.get('lat') is not None else request.data.get('latitude')
        lng = request.data.get('lng') if request.data.get('lng') is not None else request.data.get('longitude')
        accuracy = request.data.get('accuracy') if request.data.get('accuracy') is not None else request.data.get('gps_accuracy_m')
        is_mock = request.data.get('is_mock', False)
        if isinstance(is_mock, str):
            is_mock = is_mock.lower() in ('true', '1', 't')

        if lat is None or lng is None:
            return Response({"error": "GPS coordinates (lat, lng) are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lat = float(lat)
            lng = float(lng)
            accuracy = float(accuracy) if accuracy is not None else 10.0
        except ValueError:
            return Response({"error": "Invalid GPS coordinate or accuracy value."}, status=status.HTTP_400_BAD_REQUEST)

        # Max allowed accuracy from Site
        allowed_accuracy = getattr(site, 'max_gps_accuracy_m', 50.0) or 50.0
        allowed_accuracy = min(allowed_accuracy, float(site.geofence_radius_m))
        if accuracy > allowed_accuracy:
            return Response(
                {"error": f"GPS accuracy too low ({accuracy}m > {allowed_accuracy}m limit). Please move to open sky."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Geofence Distance Check
        if site.latitude is not None and site.longitude is not None:
            is_inside, dist_m = is_within_geofence(
                lat, lng, float(site.latitude), float(site.longitude),
                radius_m=float(site.geofence_radius_m), tolerance_m=0.05
            )
            if not is_inside:
                return Response({
                    "error": "Worker is outside the site geofence.",
                    "distance_m": round(dist_m, 2),
                    "geofence_radius_m": site.geofence_radius_m
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            dist_m = 0.0

        # Mock location handling
        mock_flag = bool(is_mock)
        mock_policy = getattr(settings_obj, 'mock_location_policy', 'REJECT') if settings_obj else 'REJECT'
        if mock_flag and mock_policy == 'REJECT':
            return Response({"error": "Mock location detected and rejected by society policy."}, status=status.HTTP_400_BAD_REQUEST)

        # ── Selfie Photo Validation ──
        selfie_file = request.FILES.get('selfie')
        selfie_required = getattr(settings_obj, 'selfie_required', False) if settings_obj else False

        if selfie_required and not selfie_file:
            return Response({"error": "Selfie photo is required for clock-in."}, status=status.HTTP_400_BAD_REQUEST)

        if selfie_file:
            # Check file size (max 5 MB)
            if selfie_file.size > 5 * 1024 * 1024:
                return Response({"error": "Selfie image exceeds 5MB size limit."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Open with Pillow, verify it decodes as an image and strip EXIF
                image = Image.open(selfie_file)
                image.verify()

                # Re-open for stripping metadata and re-saving
                selfie_file.seek(0)
                image = Image.open(selfie_file)
                data = list(image.getdata())
                clean_img = Image.new(image.mode, image.size)
                clean_img.putdata(data)

                out_io = io.BytesIO()
                clean_img.save(out_io, format='JPEG', quality=85)
                out_io.seek(0)
                from django.core.files.uploadedfile import InMemoryUploadedFile
                selfie_file = InMemoryUploadedFile(
                    out_io, None, f"{clock_in_uuid.hex}.jpg",
                    'image/jpeg', out_io.getbuffer().nbytes, None
                )
            except Exception:
                return Response({"error": "Invalid or corrupted image file."}, status=status.HTTP_400_BAD_REQUEST)

        # ── Timestamp Drift & Offline Sync Handling ──
        client_ts_raw = request.data.get('client_timestamp')
        client_ts = parse_datetime(client_ts_raw) if client_ts_raw else None
        if not client_ts:
            client_ts = now

        if timezone.is_naive(client_ts):
            client_ts = timezone.make_aware(client_ts)

        drift = abs((client_ts - now).total_seconds())
        time_mismatch = drift > 600.0  # > 10 minutes tolerance

        # Never record offline sync as server 'now'
        clock_in_time = client_ts

        # ── Lateness Check ──
        grace_mins = getattr(settings_obj, 'shift_start_grace_minutes', 15) if settings_obj else 15
        late_threshold = slot.shift_start_at + timedelta(minutes=grace_mins)
        flags = []
        if clock_in_time > late_threshold:
            flags.append('LATE')
            Alert.objects.get_or_create(
                society=slot.society,
                roster_entry=slot,
                alert_type='LATE',
                defaults={'notes': f"Worker clocked in late at {clock_in_time.strftime('%H:%M')} (grace: {grace_mins}m)."}
            )

        # ── Persist AttendanceEvent & Update Slot Status ──
        try:
            with transaction.atomic():
                attendance_event = AttendanceEvent.objects.create(
                    society=slot.society,
                    roster_entry=slot,
                    worker=worker,
                    clock_in_uuid=clock_in_uuid,
                    clock_in_at=clock_in_time,
                    client_timestamp=client_ts,
                    time_mismatch_flag=time_mismatch,
                    latitude=Decimal(str(round(lat, 6))),
                    longitude=Decimal(str(round(lng, 6))),
                    gps_accuracy_m=round(accuracy, 2),
                    distance_from_site_m=round(dist_m, 2),
                    mock_location_flag=mock_flag,
                    selfie_file=selfie_file,
                    flags=','.join(flags)
                )
                slot.status = 'PRESENT'
                slot.save(update_fields=['status'])
        except IntegrityError:
            # Slot already clocked in concurrently or unique constraint violated
            return Response(
                {"error": "This roster slot already has an attendance record."},
                status=status.HTTP_409_CONFLICT
            )

        serializer = AttendanceEventSerializer(attendance_event)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RosterClockOutView(APIView):
    """
    POST /api/roster/clock-out/
    Clock out of an active roster shift, calculating worked minutes, early leave, and overtime.
    Restricted to: WORKER only.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'clock_out'

    def post(self, request):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        clock_out_uuid_str = request.data.get('clock_out_uuid')
        if not clock_out_uuid_str:
            return Response({"error": "clock_out_uuid is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            clock_out_uuid = uuid.UUID(str(clock_out_uuid_str))
        except ValueError:
            return Response({"error": "Invalid clock_out_uuid format."}, status=status.HTTP_400_BAD_REQUEST)

        # ── Idempotency Check (Scoped to this worker) ──
        existing = AttendanceEvent.objects.filter(worker=worker, clock_out_uuid=clock_out_uuid).first()
        if existing:
            serializer = AttendanceEventSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Find open attendance event for this worker
        roster_entry_id = request.data.get('roster_entry_id')
        qs = AttendanceEvent.objects.filter(worker=worker, clock_out_at__isnull=True).select_related(
            'roster_entry__shift', 'roster_entry__society__settings'
        )
        if roster_entry_id:
            qs = qs.filter(roster_entry_id=roster_entry_id)

        event = qs.order_by('-clock_in_at').first()
        if not event:
            return Response({"error": "No active clocked-in session found to clock out."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        client_ts_raw = request.data.get('client_timestamp')
        client_ts = parse_datetime(client_ts_raw) if client_ts_raw else None
        if not client_ts:
            client_ts = now

        if timezone.is_naive(client_ts):
            client_ts = timezone.make_aware(client_ts)

        drift = abs((client_ts - now).total_seconds())
        if drift > 600.0:
            event.time_mismatch_flag = True

        clock_out_time = client_ts
        slot = event.roster_entry
        settings_obj = getattr(slot.society, 'settings', None)

        worked_seconds = (clock_out_time - event.clock_in_at).total_seconds()
        worked_minutes = max(0, int(worked_seconds / 60))

        # Check early leave and overtime
        flags = [f for f in event.flags.split(',') if f]
        early_mins = getattr(settings_obj, 'early_leave_minutes', 15) if settings_obj else 15
        overtime_mins = getattr(settings_obj, 'overtime_threshold_minutes', 30) if settings_obj else 30

        if clock_out_time < slot.shift_end_at - timedelta(minutes=early_mins):
            if 'EARLY_LEAVE' not in flags:
                flags.append('EARLY_LEAVE')

        if clock_out_time > slot.shift_end_at + timedelta(minutes=overtime_mins):
            if 'OVERTIME' not in flags:
                flags.append('OVERTIME')

        with transaction.atomic():
            event.clock_out_uuid = clock_out_uuid
            event.clock_out_at = clock_out_time
            event.worked_minutes = worked_minutes
            event.flags = ','.join(flags)
            event.save(update_fields=['clock_out_uuid', 'clock_out_at', 'worked_minutes', 'flags', 'time_mismatch_flag'])

            slot.status = 'COMPLETED'
            slot.save(update_fields=['status'])

        serializer = AttendanceEventSerializer(event)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AttendanceCorrectionView(APIView):
    """
    POST /api/roster/attendance/{id}/correct/
    Supervisor/Director attendance correction endpoint.
    Requires an explicit reason and records an immutable AuditLog entry.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def post(self, request, pk):
        try:
            event = AttendanceEvent.objects.select_related('society').get(pk=pk)
        except AttendanceEvent.DoesNotExist:
            raise Http404

        # Cross-society check for supervisor
        if request.user.role == 'SUPERVISOR':
            user_soc_ids = [str(s) for s in get_user_society_ids(request.user)]
            if str(event.society_id) not in user_soc_ids:
                raise Http404

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({"error": "A non-empty reason is required for attendance correction."}, status=status.HTTP_400_BAD_REQUEST)

        old_data = {
            "clock_in_at": event.clock_in_at.isoformat() if event.clock_in_at else None,
            "clock_out_at": event.clock_out_at.isoformat() if event.clock_out_at else None,
            "flags": event.flags,
            "worked_minutes": event.worked_minutes
        }

        new_clock_in = request.data.get('clock_in_at')
        new_clock_out = request.data.get('clock_out_at')
        new_flags = request.data.get('flags')

        if new_clock_in:
            parsed = parse_datetime(new_clock_in)
            if parsed:
                event.clock_in_at = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed

        if new_clock_out:
            parsed = parse_datetime(new_clock_out)
            if parsed:
                event.clock_out_at = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed

        if new_flags is not None:
            event.flags = new_flags

        if event.clock_in_at and event.clock_out_at:
            event.worked_minutes = max(0, int((event.clock_out_at - event.clock_in_at).total_seconds() / 60))

        with transaction.atomic():
            event.save()
            new_data = {
                "clock_in_at": event.clock_in_at.isoformat() if event.clock_in_at else None,
                "clock_out_at": event.clock_out_at.isoformat() if event.clock_out_at else None,
                "flags": event.flags,
                "worked_minutes": event.worked_minutes
            }
            AuditLog.objects.create(
                society=event.society,
                actor=request.user,
                action='ATTENDANCE_CORRECTION',
                target_model='AttendanceEvent',
                target_id=event.id,
                changes={"before": old_data, "after": new_data},
                reason=reason
            )

        return Response(AttendanceEventSerializer(event).data, status=status.HTTP_200_OK)


class SelfieDownloadView(APIView):
    """
    GET /api/roster/attendance/{id}/selfie/
    Permission-checked endpoint for worker selfies. Never serves guessable public URLs.
    Cross-society access returns 404.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'selfie'

    def get(self, request, pk):
        try:
            event = AttendanceEvent.objects.select_related('society', 'worker__user').get(pk=pk)
        except AttendanceEvent.DoesNotExist:
            raise Http404

        role = getattr(request.user, 'role', '')
        user_soc_ids = [str(s) for s in get_user_society_ids(request.user)]

        # Permission matrix
        if role == 'DIRECTOR':
            pass
        elif role == 'SUPERVISOR':
            if str(event.society_id) not in user_soc_ids:
                raise Http404
        elif role == 'WORKER':
            if event.worker.user != request.user:
                raise Http404
        else:
            # Chairman & Member are strictly denied worker selfies
            raise Http404

        if not event.selfie_file:
            raise Http404

        try:
            return FileResponse(event.selfie_file.open('rb'), content_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})
        except Exception:
            raise Http404


# ─── VIEWSETS WITH SOCIETY SCOPING ──────────────────────────────────────────

class PostViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = Post.objects.select_related('site', 'society').all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def get_permissions(self):
        role = getattr(self.request.user, 'role', '')
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if role not in ['DIRECTOR', 'SUPERVISOR']:
                from rest_framework.permissions import BasePermission
                class Deny(BasePermission):
                    def has_permission(self, r, v): return False
                return [Deny()]
        return super().get_permissions()


class ShiftViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = Shift.objects.select_related('post__site', 'society').all()
    serializer_class = ShiftSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def get_permissions(self):
        role = getattr(self.request.user, 'role', '')
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if role not in ['DIRECTOR', 'SUPERVISOR']:
                from rest_framework.permissions import BasePermission
                class Deny(BasePermission):
                    def has_permission(self, r, v): return False
                return [Deny()]
        return super().get_permissions()


class RosterAssignmentViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = RosterAssignment.objects.select_related('worker__user', 'shift__post', 'society').all()
    serializer_class = RosterAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def perform_create(self, serializer):
        society = self.resolve_create_society(self.request)
        serializer.save(society=society, created_by=self.request.user)


class DailyRosterViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DailyRoster.objects.select_related('post__site', 'shift', 'worker__user', 'covered_by__user', 'society').all()
    serializer_class = DailyRosterSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def get_queryset(self):
        qs = super().get_queryset()
        site_id = self.request.query_params.get('site')
        date_str = self.request.query_params.get('date')
        if site_id:
            qs = qs.filter(post__site_id=site_id)
        if date_str:
            target_date = parse_date(date_str)
            if target_date:
                qs = qs.filter(date=target_date)
        return qs


class LeaveRecordViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = LeaveRecord.objects.select_related('worker__user', 'approved_by', 'society').all()
    serializer_class = LeaveRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def perform_create(self, serializer):
        society = self.resolve_create_society(self.request)
        serializer.save(society=society)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsOpsUser])
    def approve(self, request, pk=None):
        leave = self.get_object()
        leave.status = 'APPROVED'
        leave.approved_by = request.user
        leave.save(update_fields=['status', 'approved_by', 'updated_at'])

        # Amendment 4: Approving leave on an existing future slot sets it UNFILLED and creates an alert
        now = timezone.now()
        future_slots = DailyRoster.objects.filter(
            worker=leave.worker,
            date__gte=leave.start_date,
            date__lte=leave.end_date,
            shift_start_at__gt=now,
            attendance_event__isnull=True
        )
        for slot in future_slots:
            slot.worker = None
            slot.status = 'UNFILLED'
            slot.save(update_fields=['worker', 'status', 'updated_at'])
            Alert.objects.get_or_create(
                society=slot.society,
                roster_entry=slot,
                alert_type='UNFILLED',
                defaults={'notes': f"Worker {leave.worker.user.username} approved for {leave.leave_type}; slot marked unfilled."}
            )
            if not ReplacementRequest.objects.filter(roster_entry=slot, status__in=['OPEN', 'OFFERING', 'ESCALATED']).exists():
                ReplacementRequest.objects.create(
                    society=slot.society,
                    roster_entry=slot,
                    reason='LEAVE',
                    status='OPEN',
                    created_by=request.user
                )

        return Response(LeaveRecordSerializer(leave).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsOpsUser])
    def reject(self, request, pk=None):
        leave = self.get_object()
        leave.status = 'REJECTED'
        leave.approved_by = request.user
        leave.save(update_fields=['status', 'approved_by', 'updated_at'])
        return Response(LeaveRecordSerializer(leave).data, status=status.HTTP_200_OK)


class AlertViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Alert.objects.select_related('roster_entry__post', 'roster_entry__shift', 'society').all()
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]
    society_field = 'society'


class AuditLogViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('actor', 'society').all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]
    society_field = 'society'


# ─── SPECIALIZED BOARD & SCHEDULE ENDPOINTS ─────────────────────────────────

class RosterBoardTodayView(APIView):
    """
    GET /api/roster/today/?site=ID
    Daily staffing board per post and shift with filled, late, absent, and unfilled slots.
    Client roles (Chairman, Member) receive worker name and photo only; phone/docs omitted.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        site_id = request.query_params.get('site')
        if not site_id:
            return Response({"error": "site query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        site = get_object_or_404(Site, id=site_id)
        role = getattr(request.user, 'role', '')

        # Cross-society check
        if role != 'DIRECTOR':
            user_soc_ids = [str(s) for s in get_user_society_ids(request.user)]
            if str(site.society_id) not in user_soc_ids:
                raise Http404

        target_date = parse_date(request.query_params.get('date', '')) or timezone.localdate()

        slots = DailyRoster.objects.filter(
            post__site=site,
            date=target_date
        ).select_related('post', 'shift', 'worker__user', 'covered_by__user').prefetch_related('attendance_event')

        posts_data = {}
        for slot in slots:
            p_id = str(slot.post.id)
            if p_id not in posts_data:
                posts_data[p_id] = {
                    "post_id": p_id,
                    "post_name": slot.post.name,
                    "shifts": {}
                }
            s_id = str(slot.shift.id)
            if s_id not in posts_data[p_id]["shifts"]:
                posts_data[p_id]["shifts"][s_id] = {
                    "shift_id": s_id,
                    "shift_name": slot.shift.name,
                    "start_time": slot.shift.start_time.strftime('%H:%M'),
                    "end_time": slot.shift.end_time.strftime('%H:%M'),
                    "slots": []
                }

            w = slot.covered_by or slot.worker
            posts_data[p_id]["shifts"][s_id]["slots"].append({
                "slot_id": str(slot.id),
                "slot_number": slot.slot_number,
                "status": slot.status,
                "worker": {
                    "id": str(w.id) if w else None,
                    "name": (f"{w.user.first_name} {w.user.last_name}".strip() or w.user.username) if w else None,
                    "photo": w.profile_photo.url if w and w.profile_photo else None
                } if w else None,
                "has_clock_in": hasattr(slot, 'attendance_event') and bool(slot.attendance_event.clock_in_at),
                "is_late": hasattr(slot, 'attendance_event') and 'LATE' in (slot.attendance_event.flags or '')
            })

        # Format output
        results = []
        for p in posts_data.values():
            p["shifts"] = list(p["shifts"].values())
            results.append(p)

        return Response({
            "site": site.name,
            "date": target_date.isoformat(),
            "posts": results
        })


class MyScheduleView(APIView):
    """
    GET /api/roster/my-schedule/
    Worker's upcoming shift assignments.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def get(self, request):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        upcoming_slots = DailyRoster.objects.filter(
            worker=worker,
            date__gte=now.date()
        ).select_related('post__site__society', 'shift').order_by('date', 'shift_start_at')[:20]

        items = []
        for slot in upcoming_slots:
            site = slot.post.site if hasattr(slot.post, 'site') else None
            items.append({
                "roster_entry_id": str(slot.id),
                "society_name": slot.society.name,
                "site_name": site.name if site else slot.post.name,
                "site_latitude": float(site.latitude) if site and site.latitude is not None else None,
                "site_longitude": float(site.longitude) if site and site.longitude is not None else None,
                "geofence_radius_m": float(site.geofence_radius_m) if site and site.geofence_radius_m is not None else 100.0,
                "post_name": slot.post.name,
                "shift_name": slot.shift.name,
                "date": slot.date.isoformat(),
                "shift_start_at": slot.shift_start_at.isoformat(),
                "shift_end_at": slot.shift_end_at.isoformat(),
                "status": slot.status
            })

        return Response(items)


class MarkSlotAbsentView(APIView):
    """
    POST /api/roster/{id}/mark-absent/
    Supervisor marks a roster slot ABSENT.
    Amendment 3: Only marks ABSENT if worker was assigned and did not clock in and has no approved leave.
    Unfilled slots stay UNFILLED with an alert.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def post(self, request, pk):
        try:
            slot = DailyRoster.objects.select_related('society', 'worker__user').get(pk=pk)
        except DailyRoster.DoesNotExist:
            raise Http404

        # Cross-society check
        if request.user.role == 'SUPERVISOR':
            user_soc_ids = [str(s) for s in get_user_society_ids(request.user)]
            if str(slot.society_id) not in user_soc_ids:
                raise Http404

        if hasattr(slot, 'attendance_event') and slot.attendance_event.clock_in_at:
            return Response({"error": "Cannot mark absent — worker has already clocked in."}, status=status.HTTP_400_BAD_REQUEST)

        notes = request.data.get('notes', 'Marked absent by supervisor.')

        if slot.worker is not None:
            # Check approved leave
            has_approved_leave = LeaveRecord.objects.filter(
                worker=slot.worker,
                start_date__lte=slot.date,
                end_date__gte=slot.date,
                status='APPROVED'
            ).exists()

            if has_approved_leave:
                slot.worker = None
                slot.status = 'UNFILLED'
                slot.save(update_fields=['worker', 'status', 'updated_at'])
                Alert.objects.get_or_create(
                    society=slot.society,
                    roster_entry=slot,
                    alert_type='UNFILLED',
                    defaults={'notes': 'Worker on approved leave; slot kept unfilled.'}
                )
                req_reason = 'LEAVE'
            else:
                slot.status = 'ABSENT'
                slot.save(update_fields=['status', 'updated_at'])
                Alert.objects.get_or_create(
                    society=slot.society,
                    roster_entry=slot,
                    alert_type='ABSENT',
                    defaults={'notes': notes}
                )
                req_reason = 'ABSENT'
        else:
            # Empty slot stays UNFILLED
            slot.status = 'UNFILLED'
            slot.save(update_fields=['status', 'updated_at'])
            Alert.objects.get_or_create(
                society=slot.society,
                roster_entry=slot,
                alert_type='UNFILLED',
                defaults={'notes': 'Slot unassigned and unfilled.'}
            )
            req_reason = 'UNFILLED'

        if not ReplacementRequest.objects.filter(roster_entry=slot, status__in=['OPEN', 'OFFERING', 'ESCALATED']).exists():
            ReplacementRequest.objects.create(
                society=slot.society,
                roster_entry=slot,
                reason=req_reason,
                status='OPEN',
                created_by=request.user
            )

        return Response(DailyRosterSerializer(slot).data, status=status.HTTP_200_OK)


class UnfilledRosterView(APIView):
    """
    GET /api/roster/unfilled/
    Returns unfilled and absent slots across the user's active societies.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def get(self, request):
        qs = DailyRoster.objects.filter(status__in=['UNFILLED', 'ABSENT']).select_related(
            'post__site', 'shift', 'society', 'worker__user'
        )
        if request.user.role == 'SUPERVISOR':
            user_soc_ids = get_user_society_ids(request.user)
            qs = qs.filter(society__in=user_soc_ids)

        date_str = request.query_params.get('date')
        if date_str:
            target_date = parse_date(date_str)
            if target_date:
                qs = qs.filter(date=target_date)

        return Response(DailyRosterSerializer(qs.order_by('date', 'shift_start_at')[:100], many=True).data)


# ─── REPLACEMENT WORKFLOW VIEWSETS & ENDPOINTS ───────────────────────────────

class ReplacementRequestViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    CRUD and operational actions on ReplacementRequest.
    Scoped by society; Ops users (Supervisor/Director) only.
    """
    queryset = ReplacementRequest.objects.select_related(
        'society', 'roster_entry__post__site', 'roster_entry__shift', 'filled_by_worker__user'
    ).prefetch_related('offers__worker__user').all()
    serializer_class = ReplacementRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]
    society_field = 'society'

    @action(detail=True, methods=['get'])
    def candidates(self, request, pk=None):
        """
        GET /api/roster/replacements/{id}/candidates/
        Returns ranked eligible reliever workers based on bench availability,
        category match, home proximity (never live GPS), reliability history,
        and weekly workload.
        """
        req = self.get_object()
        ranked = rank_replacement_candidates(req)
        return Response(ranked)

    @action(detail=True, methods=['post'], url_path='dispatch-offers')
    def dispatch_offers(self, request, pk=None):
        """
        POST /api/roster/replacements/{id}/dispatch-offers/
        Body: {"worker_ids": ["uuid", ...]}
        Dispatches offers with expiry timer and in-app notifications.
        Audited in AuditLog.
        """
        req = self.get_object()
        if req.status not in ['OPEN', 'OFFERING', 'ESCALATED']:
            return Response(
                {"error": f"Cannot dispatch offers for replacement in status '{req.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        worker_ids = request.data.get('worker_ids', [])
        if not worker_ids or not isinstance(worker_ids, list):
            return Response({"error": "worker_ids must be a non-empty list of UUIDs."}, status=status.HTTP_400_BAD_REQUEST)

        settings_obj = getattr(req.society, 'settings', None)
        expiry_min = getattr(settings_obj, 'replacement_offer_expiry_minutes', 15) if settings_obj else 15
        now = timezone.now()
        expires_at = now + timedelta(minutes=expiry_min)

        dispatched = []
        for wid in worker_ids:
            try:
                worker = WorkerProfile.objects.select_related('user').get(id=wid)
            except (WorkerProfile.DoesNotExist, ValueError):
                continue

            is_blocked, reason, _ = check_worker_hard_blocks(worker, req.roster_entry)
            if is_blocked:
                continue

            offer, created = ReplacementOffer.objects.get_or_create(
                request=req,
                worker=worker,
                defaults={
                    'society': req.society,
                    'expires_at': expires_at,
                    'status': 'OFFERED'
                }
            )
            if created:
                Notification.objects.create(
                    society=req.society,
                    recipient=worker.user,
                    notification_type='REPLACEMENT_OFFER',
                    title='Shift Replacement Offer',
                    body=f"Replacement available at {req.roster_entry.post.name} ({req.roster_entry.shift.name}) on {req.roster_entry.date}.",
                    related_model='ReplacementOffer',
                    related_id=offer.id
                )
                dispatched.append(str(worker.id))

        if not dispatched and not req.offers.filter(status='OFFERED').exists():
            return Response(
                {"error": "No eligible offers could be dispatched. Workers may have hard blocks or invalid IDs."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if req.status == 'OPEN':
            req.status = 'OFFERING'
            req.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            society=req.society,
            actor=request.user,
            action='DISPATCH_REPLACEMENT_OFFERS',
            target_model='ReplacementRequest',
            target_id=req.id,
            changes={'dispatched_workers': dispatched, 'expires_at': expires_at.isoformat()},
            reason='Dispatched replacement offers'
        )

        return Response(ReplacementRequestSerializer(req).data)

    @action(detail=True, methods=['post'], url_path='direct-assign')
    def direct_assign(self, request, pk=None):
        """
        POST /api/roster/replacements/{id}/direct-assign/
        Body: {"worker_id": "uuid", "acknowledge_warnings": bool, "director_override_reason": str}
        Hard blocks cannot be bypassed. Warnings require acknowledgment.
        Director override requires a reason.
        """
        req = self.get_object()
        if req.status in ['FILLED', 'CANCELLED']:
            return Response(
                {"error": f"Cannot direct-assign replacement in status '{req.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "worker_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        worker = get_object_or_404(WorkerProfile, id=worker_id)
        ack_warnings = request.data.get('acknowledge_warnings', False)
        director_override = request.data.get('director_override_reason', '').strip()

        is_blocked, block_reason, warnings = check_worker_hard_blocks(worker, req.roster_entry)
        if is_blocked:
            return Response({"error": f"Hard block: {block_reason}"}, status=status.HTTP_400_BAD_REQUEST)

        if warnings:
            if request.user.role == 'DIRECTOR':
                if not director_override and not ack_warnings:
                    return Response({
                        "error": "Director override reason or warning acknowledgment required.",
                        "warnings": warnings
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                if not ack_warnings:
                    return Response({
                        "error": "Warnings must be acknowledged to proceed with assignment.",
                        "warnings": warnings
                    }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            slot = req.roster_entry
            slot.covered_by = worker
            slot.status = 'COVERED'
            slot.save(update_fields=['covered_by', 'status', 'updated_at'])

            req.status = 'FILLED'
            req.filled_by_worker = worker
            req.filled_at = timezone.now()
            req.save(update_fields=['status', 'filled_by_worker', 'filled_at', 'updated_at'])

            # Withdraw any pending offers
            req.offers.filter(status='OFFERED').update(status='WITHDRAWN')

            AuditLog.objects.create(
                society=req.society,
                actor=request.user,
                action='DIRECT_ASSIGN_REPLACEMENT',
                target_model='ReplacementRequest',
                target_id=req.id,
                changes={'worker_id': str(worker.id), 'slot_id': str(slot.id), 'warnings': warnings},
                reason=director_override or f"Direct assigned by {request.user.role} with warnings acknowledged."
            )

        return Response(ReplacementRequestSerializer(req).data)

    @action(detail=True, methods=['post'], url_path='confirm-by-phone')
    def confirm_by_phone(self, request, pk=None):
        """
        POST /api/roster/replacements/{id}/confirm-by-phone/
        Body: {"worker_id": "uuid", "notes": str}
        Supervisor confirms replacement verbally over phone.
        Audited action. Hard blocks strictly enforced.
        """
        req = self.get_object()
        if req.status in ['FILLED', 'CANCELLED']:
            return Response(
                {"error": f"Cannot confirm replacement in status '{req.status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', '').strip()
        if not notes:
            return Response({"error": "Phone confirmation notes are required."}, status=status.HTTP_400_BAD_REQUEST)

        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "worker_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        worker = get_object_or_404(WorkerProfile, id=worker_id)
        is_blocked, block_reason, warnings = check_worker_hard_blocks(worker, req.roster_entry)
        if is_blocked:
            return Response({"error": f"Hard block: {block_reason}"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            slot = req.roster_entry
            slot.covered_by = worker
            slot.status = 'COVERED'
            slot.save(update_fields=['covered_by', 'status', 'updated_at'])

            req.status = 'FILLED'
            req.filled_by_worker = worker
            req.filled_at = timezone.now()
            req.save(update_fields=['status', 'filled_by_worker', 'filled_at', 'updated_at'])

            req.offers.filter(status='OFFERED').update(status='WITHDRAWN')

            AuditLog.objects.create(
                society=req.society,
                actor=request.user,
                action='CONFIRM_BY_PHONE',
                target_model='ReplacementRequest',
                target_id=req.id,
                changes={'worker_id': str(worker.id), 'slot_id': str(slot.id)},
                reason=notes
            )

        return Response(ReplacementRequestSerializer(req).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        POST /api/roster/replacements/{id}/cancel/
        Body: {"reason": str}
        Cancels replacement request. If slot was COVERED, restores it to SCHEDULED/UNFILLED
        and re-enables original worker clock-in.
        """
        req = self.get_object()
        reason = request.data.get('reason', 'Cancelled by supervisor')

        with transaction.atomic():
            slot = req.roster_entry
            if slot.status == 'COVERED':
                slot.covered_by = None
                slot.status = 'SCHEDULED' if slot.worker else 'UNFILLED'
                slot.save(update_fields=['covered_by', 'status', 'updated_at'])

            req.status = 'CANCELLED'
            req.save(update_fields=['status', 'updated_at'])

            req.offers.filter(status='OFFERED').update(status='WITHDRAWN')

            AuditLog.objects.create(
                society=req.society,
                actor=request.user,
                action='CANCEL_REPLACEMENT',
                target_model='ReplacementRequest',
                target_id=req.id,
                changes={'slot_id': str(slot.id), 'restored_status': slot.status},
                reason=reason
            )

        return Response(ReplacementRequestSerializer(req).data)


class MyOffersView(APIView):
    """
    GET /api/roster/my-offers/
    Returns active, unexpired replacement offers dispatched to the authenticated worker.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def get(self, request):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        offers = ReplacementOffer.objects.filter(
            worker=worker,
            status='OFFERED',
            expires_at__gt=now
        ).select_related(
            'request__roster_entry__post__site',
            'request__roster_entry__shift',
            'society'
        )
        return Response(ReplacementOfferSerializer(offers, many=True).data)


class AcceptOfferView(APIView):
    """
    POST /api/roster/offers/{id}/accept/
    Worker accepts an active replacement offer.
    Amendment 3: Enforces DB-level concurrency via atomic conditional update checking rows affected.
    If another worker accepted first, returns HTTP 409 Conflict immediately.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def post(self, request, pk):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            offer = ReplacementOffer.objects.select_related('request__roster_entry', 'society').get(pk=pk, worker=worker)
        except ReplacementOffer.DoesNotExist:
            raise Http404

        now = timezone.now()
        if offer.expires_at <= now:
            return Response({"error": "Offer has expired."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Conditional atomic update: first accept wins, rows == 0 returns 409
            rows = ReplacementOffer.objects.filter(
                id=offer.id,
                status='OFFERED',
                expires_at__gt=now,
                request__status__in=['OPEN', 'OFFERING', 'ESCALATED']
            ).update(status='ACCEPTED', responded_at=now)

            if rows == 0:
                return Response(
                    {"error": "Offer is no longer available or another worker has already accepted."},
                    status=status.HTTP_409_CONFLICT
                )

            offer.refresh_from_db()
            req = offer.request
            slot = req.roster_entry

            # Set slot to COVERED by this worker
            slot.covered_by = worker
            slot.status = 'COVERED'
            slot.save(update_fields=['covered_by', 'status', 'updated_at'])

            # Set request to FILLED
            req.status = 'FILLED'
            req.filled_by_worker = worker
            req.filled_at = now
            req.save(update_fields=['status', 'filled_by_worker', 'filled_at', 'updated_at'])

            # Withdraw all other pending offers for this request
            ReplacementOffer.objects.filter(request=req, status='OFFERED').exclude(id=offer.id).update(status='WITHDRAWN')

            # Audit acceptance
            AuditLog.objects.create(
                society=req.society,
                actor=request.user,
                action='ACCEPT_OFFER',
                target_model='ReplacementOffer',
                target_id=offer.id,
                changes={'worker': worker.user.username, 'slot_id': str(slot.id)},
                reason='Replacement offer accepted by worker'
            )

        return Response(ReplacementOfferSerializer(offer).data, status=status.HTTP_200_OK)


class DeclineOfferView(APIView):
    """
    POST /api/roster/offers/{id}/decline/
    Worker declines a replacement offer. Audited action.
    """
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    def post(self, request, pk):
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            offer = ReplacementOffer.objects.select_related('society').get(pk=pk, worker=worker)
        except ReplacementOffer.DoesNotExist:
            raise Http404

        reason = request.data.get('reason', '').strip()
        offer.status = 'DECLINED'
        offer.decline_reason = reason
        offer.responded_at = timezone.now()
        offer.save(update_fields=['status', 'decline_reason', 'responded_at', 'updated_at'])

        AuditLog.objects.create(
            society=offer.society,
            actor=request.user,
            action='DECLINE_OFFER',
            target_model='ReplacementOffer',
            target_id=offer.id,
            changes={'decline_reason': reason},
            reason=reason or 'Worker declined replacement offer'
        )

        return Response(ReplacementOfferSerializer(offer).data, status=status.HTTP_200_OK)


class ReplacementMetricsView(APIView):
    """
    GET /api/roster/replacements/metrics/?month=YYYY-MM&society=UUID
    Amendment 10: Computes non-cancelled requests denominator, fill rate %,
    fill-before-shift-start rate %, and P90 time-to-fill using nearest-rank method.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def get(self, request):
        import math
        from calendar import monthrange
        from datetime import date

        month_str = request.query_params.get('month')
        now = timezone.now()
        if not month_str:
            month_str = now.strftime('%Y-%m')

        try:
            year, month = map(int, month_str.split('-'))
            _, last_day = monthrange(year, month)
            start_d = date(year, month, 1)
            end_d = date(year, month, last_day)
        except Exception:
            return Response({"error": "Invalid month format. Expected YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)

        qs = ReplacementRequest.objects.filter(
            opened_at__date__gte=start_d,
            opened_at__date__lte=end_d
        )

        if request.user.role == 'SUPERVISOR':
            user_soc_ids = get_user_society_ids(request.user)
            qs = qs.filter(society__in=user_soc_ids)
        elif request.query_params.get('society'):
            qs = qs.filter(society_id=request.query_params.get('society'))

        non_cancelled = qs.exclude(status='CANCELLED')
        total = non_cancelled.count()
        filled_requests = list(non_cancelled.filter(status='FILLED').select_related('roster_entry'))
        filled_count = len(filled_requests)

        fill_rate_pct = round((filled_count / total * 100), 1) if total > 0 else 0.0

        fill_before_start = sum(
            1 for r in filled_requests
            if r.filled_at and r.roster_entry.shift_start_at and r.filled_at <= r.roster_entry.shift_start_at
        )
        fill_before_start_pct = round((fill_before_start / total * 100), 1) if total > 0 else 0.0

        time_deltas = [
            (r.filled_at - r.opened_at).total_seconds() / 60.0
            for r in filled_requests
            if r.filled_at and r.opened_at
        ]

        if time_deltas:
            avg_time = round(sum(time_deltas) / len(time_deltas), 1)
            sorted_deltas = sorted(time_deltas)
            # P90 Nearest-Rank method: index = ceil(0.90 * N) - 1 (0-indexed)
            p90_idx = max(0, min(len(sorted_deltas) - 1, math.ceil(0.90 * len(sorted_deltas)) - 1))
            p90_time = round(sorted_deltas[p90_idx], 1)
        else:
            avg_time = None
            p90_time = None

        return Response({
            "month": month_str,
            "total_non_cancelled": total,
            "filled_count": filled_count,
            "fill_rate_pct": fill_rate_pct,
            "fill_before_shift_start_count": fill_before_start,
            "fill_before_shift_start_pct": fill_before_start_pct,
            "avg_time_to_fill_minutes": avg_time,
            "p90_time_to_fill_minutes": p90_time,
            "p90_method": "nearest_rank (sorted_deltas[ceil(0.90 * N) - 1])"
        })


class NotificationViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    List and manage in-app notifications for the authenticated user.
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    society_field = 'society'

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(recipient=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notif = self.get_object()
        notif.read_at = timezone.now()
        notif.save(update_fields=['read_at'])
        return Response(NotificationSerializer(notif).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"status": "All notifications marked as read."})


