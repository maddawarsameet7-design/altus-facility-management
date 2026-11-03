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
    Membership
)
from .mixins import SocietyScopedMixin, get_user_society_ids
from .permissions import IsWorker, IsOpsUser, IsDirectorOnly
from .staffing_utils import is_within_geofence
from .serializers_staffing import (
    PostSerializer, ShiftSerializer, RosterAssignmentSerializer,
    DailyRosterSerializer, LeaveRecordSerializer, AttendanceEventSerializer,
    AlertSerializer, AuditLogSerializer
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

            # Ensure slot is assigned to this worker or covering
            if slot.worker_id != worker.id and slot.covered_by_id != worker.id:
                return Response({"error": "You are not assigned to this roster slot."}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Deterministic slot resolution for the current time window
            # Window: [shift_start_at - early_window, shift_end_at]
            eligible_slots = DailyRoster.objects.filter(
                worker=worker,
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
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        accuracy = request.data.get('accuracy')
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
            items.append({
                "roster_entry_id": str(slot.id),
                "society_name": slot.society.name,
                "site_name": slot.post.site.name,
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
            else:
                slot.status = 'ABSENT'
                slot.save(update_fields=['status', 'updated_at'])
                Alert.objects.get_or_create(
                    society=slot.society,
                    roster_entry=slot,
                    alert_type='ABSENT',
                    defaults={'notes': notes}
                )
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

