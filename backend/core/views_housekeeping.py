import calendar
import json
import os
import uuid
import zoneinfo
from datetime import datetime, time, timedelta, timezone as dt_tz
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q, Prefetch
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from core.mixins import SocietyScopedMixin
from core.models import (
    Area, TaskTemplate, TaskInstance, TaskPhoto,
    Inspection, InspectionPhoto, Complaint,
    SupplyItem, SupplyRequest, QualityScoreSnapshot,
    Site, Post, Shift, DailyRoster, AttendanceEvent,
    WorkerProfile, User, Membership, Alert, AuditLog, Notification
)
from core.permissions import (
    IsWorker, IsSupervisor, IsDirector, IsOpsUser, IsClientUser
)
from core.serializers_housekeeping import (
    AreaSerializer, TaskTemplateSerializer, TaskInstanceSerializer,
    TaskPhotoSerializer, InspectionSerializer, ComplaintSerializer,
    SupplyItemSerializer, SupplyRequestSerializer, QualityScoreSnapshotSerializer
)
from core.housekeeping_utils import (
    process_and_sanitize_image, validate_photo_capture_gps,
    calculate_monthly_quality_score, create_or_get_quality_score_snapshot
)


def _to_json_safe(data):
    """Recursively serializes data containing UUIDs, Decimals, dates to standard JSON."""
    if data is None:
        return {}
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def _parse_client_timestamp(ts_str: Optional[str]) -> datetime:
    """Parses ISO timestamp or defaults to timezone.now()."""
    if ts_str:
        parsed = parse_datetime(str(ts_str))
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, dt_tz.utc)
            return parsed
    return timezone.now()


# ── 1. Area ViewSet ──────────────────────────────────────────────────────────

class AreaViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    CRUD for physical zones/areas within a site.
    Deletion guard: Areas with historical templates or task instances cannot be deleted.
    """
    queryset = Area.objects.select_related('society', 'site')
    serializer_class = AreaSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOpsUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        site = serializer.validated_data.get('site')
        society = (site.society if site else None) or self.resolve_create_society(self.request)
        serializer.save(society=society)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if TaskTemplate.objects.filter(area=instance).exists() or TaskInstance.objects.filter(area=instance).exists():
            return Response(
                {"error": "Area has linked task records and cannot be deleted. Set is_active=False instead."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


# ── 2. TaskTemplate ViewSet ──────────────────────────────────────────────────

class TaskTemplateViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    CRUD for recurring task templates.
    Amendment 5: Template edits apply to future dates only.
    Deletion guard: Templates with historical instances cannot be deleted.
    """
    queryset = TaskTemplate.objects.select_related('society', 'post', 'area', 'shift')
    serializer_class = TaskTemplateSerializer

    def get_permissions(self):
        return [permissions.IsAuthenticated(), IsOpsUser()]

    def perform_create(self, serializer):
        post = serializer.validated_data.get('post')
        society = (post.society if post else None) or self.resolve_create_society(self.request)
        template = serializer.save(society=society)
        AuditLog.objects.create(
            society=society,
            actor=self.request.user,
            action='CREATE_TASK_TEMPLATE',
            target_model='TaskTemplate',
            target_id=template.id,
            changes=_to_json_safe(serializer.data),
            reason='Template created by supervisor'
        )

    def perform_update(self, serializer):
        old_data = TaskTemplateSerializer(serializer.instance).data
        template = serializer.save()
        AuditLog.objects.create(
            society=template.society,
            actor=self.request.user,
            action='UPDATE_TASK_TEMPLATE',
            target_model='TaskTemplate',
            target_id=template.id,
            changes=_to_json_safe({'before': old_data, 'after': serializer.data}),
            reason='Template updated (applies to future dates)'
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if TaskInstance.objects.filter(template=instance).exists():
            return Response(
                {"error": "Task template has historical task instances and cannot be deleted. Set is_active=False instead."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)


# ── 3. TaskInstance ViewSet & Worker Actions ─────────────────────────────────

class TaskInstanceViewSet(SocietyScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    Housekeeping task instances and worker action lifecycle.
    """
    queryset = TaskInstance.objects.select_related(
        'society', 'template', 'post', 'shift', 'area',
        'claimed_by__user', 'completed_by__user'
    ).prefetch_related('photos')
    serializer_class = TaskInstanceSerializer

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', '')
        if role == 'WORKER':
            worker = getattr(user, 'worker_profile', None)
            if not worker:
                return TaskInstance.objects.none()
            worker_shift_ids = DailyRoster.objects.filter(
                Q(worker=worker) | Q(covered_by=worker)
            ).values_list('shift_id', flat=True)
            qs = TaskInstance.objects.filter(
                Q(shift_id__in=worker_shift_ids) |
                Q(claimed_by=worker) |
                Q(completed_by=worker)
            ).select_related(
                'society', 'template', 'post', 'shift', 'area',
                'claimed_by__user', 'completed_by__user'
            ).prefetch_related('photos')
        else:
            qs = super().get_queryset()

        # Optional query parameters
        site_id = self.request.query_params.get('site_id')
        date_str = self.request.query_params.get('date')
        post_id = self.request.query_params.get('post_id')
        area_id = self.request.query_params.get('area_id')
        status_filter = self.request.query_params.get('status')

        if site_id:
            qs = qs.filter(post__site_id=site_id)
        if date_str:
            parsed = parse_date(date_str)
            if parsed:
                qs = qs.filter(due_date=parsed)
        if post_id:
            qs = qs.filter(post_id=post_id)
        if area_id:
            qs = qs.filter(area_id=area_id)
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    @action(detail=False, methods=['get'], url_path='my-tasks')
    def my_tasks(self, request):
        """
        GET /api/housekeeping/my-tasks/
        Returns tasks for shifts the calling worker is currently scheduled or covering.
        """
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()

        # Find active slots for worker today
        active_slots = DailyRoster.objects.filter(
            Q(worker=worker, status__in=['SCHEDULED', 'PRESENT', 'COMPLETED']) | Q(covered_by=worker),
            date=today
        ).values_list('shift_id', flat=True)

        tasks = TaskInstance.objects.filter(
            shift_id__in=active_slots,
            due_date=today
        ).select_related('post', 'shift', 'area', 'claimed_by__user').prefetch_related('photos').order_by('area__name', 'name')

        serializer = TaskInstanceSerializer(tasks, many=True)
        return Response(serializer.data)

    def _validate_worker_attendance_and_shift(self, worker, task, action_dt):
        """
        Amendment 1: Eligibility for claim/start/complete/photo is judged on the
        client action timestamp falling inside the worker's attendance window (with tolerance).
        """
        # 1. Check if original worker was replaced on this shift slot
        slot = DailyRoster.objects.filter(shift=task.shift, date=task.due_date).filter(
            Q(worker=worker) | Q(covered_by=worker)
        ).first()

        if slot and slot.status == 'COVERED' and slot.covered_by_id != worker.id:
            return False, "This shift slot was reassigned to a reliever. You cannot perform tasks on it.", 409

        # 2. Check open attendance event covering action_dt (tolerance 15m)
        tolerance = timedelta(minutes=15)
        att = AttendanceEvent.objects.filter(
            worker=worker,
            roster_entry__shift=task.shift,
            clock_in_at__lte=action_dt + tolerance
        ).filter(
            Q(clock_out_at__isnull=True) | Q(clock_out_at__gte=action_dt - tolerance)
        ).first()

        if not att:
            return False, "You must be clocked in for this shift to perform this task.", 403

        return True, None, 200

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/claim/
        Amendment 3: Atomic claim via conditional update (returns 409 for loser).
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        action_dt = _parse_client_timestamp(request.data.get('action_timestamp'))
        valid, err_msg, code = self._validate_worker_attendance_and_shift(worker, task, action_dt)
        if not valid:
            return Response({"error": err_msg}, status=code)

        if task.status not in ('PENDING', 'IN_PROGRESS'):
            return Response({"error": f"Cannot claim task in status '{task.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        # Atomic conditional update
        with transaction.atomic():
            rows = TaskInstance.objects.filter(
                id=task.id,
                claimed_by__isnull=True
            ).update(
                claimed_by=worker,
                status='IN_PROGRESS',
                started_at=action_dt,
                updated_at=timezone.now()
            )

            if rows == 0:
                task.refresh_from_db()
                if task.claimed_by_id == worker.id:
                    return Response(TaskInstanceSerializer(task).data, status=status.HTTP_200_OK)
                return Response(
                    {"error": "Task has already been claimed by another worker."},
                    status=status.HTTP_409_CONFLICT
                )

        task.refresh_from_db()
        return Response(TaskInstanceSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='release')
    def release(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/release/
        Amendment 3: Worker releases a claimed task back to PENDING.
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        is_ops = request.user.role in ('SUPERVISOR', 'DIRECTOR')

        if not is_ops and (not worker or task.claimed_by_id != worker.id):
            return Response({"error": "Only the current claimant or a supervisor can release this task."}, status=status.HTTP_403_FORBIDDEN)

        if task.status not in ('PENDING', 'IN_PROGRESS'):
            return Response({"error": f"Cannot release task in status '{task.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        old_claimed_by = str(task.claimed_by_id)
        task.claimed_by = None
        task.status = 'PENDING'
        task.started_at = None
        task.save(update_fields=['claimed_by', 'status', 'started_at', 'updated_at'])

        AuditLog.objects.create(
            society=task.society,
            actor=request.user,
            action='RELEASE_TASK',
            target_model='TaskInstance',
            target_id=task.id,
            changes={'previous_claimant': old_claimed_by},
            reason=request.data.get('reason', 'Task released back to pool')
        )

        return Response(TaskInstanceSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='reassign')
    def reassign(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/reassign/
        Amendment 3: Supervisor reassigns task to another eligible worker.
        """
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Only supervisors can reassign tasks."}, status=status.HTTP_403_FORBIDDEN)

        task = self.get_object()
        worker_id = request.data.get('worker_id')
        if not worker_id:
            return Response({"error": "worker_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        new_worker = get_object_or_404(WorkerProfile, id=worker_id)
        old_worker_id = str(task.claimed_by_id) if task.claimed_by else None

        task.claimed_by = new_worker
        task.status = 'IN_PROGRESS'
        task.save(update_fields=['claimed_by', 'status', 'updated_at'])

        AuditLog.objects.create(
            society=task.society,
            actor=request.user,
            action='REASSIGN_TASK',
            target_model='TaskInstance',
            target_id=task.id,
            changes={'previous_worker': old_worker_id, 'new_worker': str(new_worker.id)},
            reason=request.data.get('reason', 'Reassigned by supervisor')
        )

        return Response(TaskInstanceSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/start/
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        action_dt = _parse_client_timestamp(request.data.get('action_timestamp'))
        valid, err_msg, code = self._validate_worker_attendance_and_shift(worker, task, action_dt)
        if not valid:
            return Response({"error": err_msg}, status=code)

        if task.claimed_by and task.claimed_by != worker:
            return Response({"error": "Task is claimed by another worker."}, status=status.HTTP_409_CONFLICT)

        task.claimed_by = worker
        task.status = 'IN_PROGRESS'
        if not task.started_at:
            task.started_at = action_dt
        task.save(update_fields=['claimed_by', 'status', 'started_at', 'updated_at'])
        return Response(TaskInstanceSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/complete/
        Amendment 2: Supports 'complete' with expected photo client_uuids:
        Task transitions to AWAITING_EVIDENCE until photos arrive, or DONE if already satisfied.
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        action_dt = _parse_client_timestamp(request.data.get('action_timestamp'))
        valid, err_msg, code = self._validate_worker_attendance_and_shift(worker, task, action_dt)
        if not valid:
            return Response({"error": err_msg}, status=code)

        expected_uuids = request.data.get('expected_photo_uuids', [])
        if not isinstance(expected_uuids, list):
            expected_uuids = []

        # Check existing photos against requirements
        existing_photos = list(task.photos.all())
        policy = getattr(task.society.settings, 'photo_geofence_policy', 'REJECT') if hasattr(task.society, 'settings') else 'REJECT'

        if policy == 'REJECT':
            valid_photos = [p for p in existing_photos if 'OUTSIDE_GEOFENCE' not in (p.flags or [])]
        else:
            valid_photos = existing_photos

        has_before = any(p.kind == 'BEFORE' for p in valid_photos)
        has_after = any(p.kind == 'AFTER' for p in valid_photos)

        req = task.photo_required
        satisfied = True
        if req == 'AFTER_ONLY' and not has_after:
            satisfied = False
        elif req == 'BEFORE_AFTER' and not (has_before and has_after):
            satisfied = False

        if not satisfied:
            if not expected_uuids:
                return Response(
                    {"error": f"Photo requirement '{req}' not satisfied. Upload required photos or provide expected_photo_uuids."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Amendment 2: Enter AWAITING_EVIDENCE
            deadline_hours = getattr(task.society.settings, 'evidence_deadline_hours', 24) if hasattr(task.society, 'settings') else 24
            task.status = 'AWAITING_EVIDENCE'
            task.expected_photo_uuids = [str(u) for u in expected_uuids]
            task.evidence_deadline = action_dt + timedelta(hours=deadline_hours)
            task.completed_by = worker
            task.completed_at = action_dt
            task.save(update_fields=['status', 'expected_photo_uuids', 'evidence_deadline', 'completed_by', 'completed_at', 'updated_at'])
            return Response(TaskInstanceSerializer(task).data, status=status.HTTP_200_OK)

        # Satisfied: mark DONE
        # Check if any photos have non-blocking flags needing review
        needs_review = any(any(f in (p.flags or []) for f in ('OUTSIDE_GEOFENCE', 'MOCK_LOCATION', 'TIME_MISMATCH')) for p in existing_photos)

        task.status = 'DONE'
        task.needs_review = needs_review
        task.completed_by = worker
        task.completed_at = action_dt
        task.save(update_fields=['status', 'needs_review', 'completed_by', 'completed_at', 'updated_at'])

        return Response(TaskInstanceSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='skip')
    def skip(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/skip/
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('skip_reason', '').strip()
        valid_reasons = ['AREA_LOCKED', 'RESIDENT_REQUEST', 'NO_SUPPLIES', 'OTHER']
        if reason not in valid_reasons:
            return Response({"error": f"Invalid skip_reason. Choose from: {valid_reasons}"}, status=status.HTTP_400_BAD_REQUEST)

        notes = request.data.get('notes', '').strip()

        task.status = 'SKIPPED'
        task.skip_reason = reason
        task.notes = f"{task.notes}\n[SKIPPED: {reason}] {notes}".strip()
        task.save(update_fields=['status', 'skip_reason', 'notes', 'updated_at'])

        return Response(TaskInstanceSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='photos')
    def upload_photo(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/photos/
        Multipart photo upload with capture GPS, accuracy, mock flag, EXIF sanitization.
        """
        task = self.get_object()
        worker = getattr(request.user, 'worker_profile', None)
        if not worker:
            return Response({"error": "Worker profile required."}, status=status.HTTP_403_FORBIDDEN)

        client_uuid_str = request.data.get('client_uuid')
        if not client_uuid_str:
            return Response({"error": "client_uuid is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client_uuid = uuid.UUID(str(client_uuid_str))
        except ValueError:
            return Response({"error": "Invalid client_uuid format."}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency check per uploader
        existing_photo = TaskPhoto.objects.filter(client_uuid=client_uuid, uploaded_by=worker).first()
        if existing_photo:
            return Response(TaskPhotoSerializer(existing_photo).data, status=status.HTTP_200_OK)

        # Check photo limit per task
        max_photos = getattr(task.society.settings, 'max_photos_per_task', 6) if hasattr(task.society, 'settings') else 6
        if task.photos.count() >= max_photos:
            return Response({"error": f"Task photo limit reached (max {max_photos} photos per task)."}, status=status.HTTP_400_BAD_REQUEST)

        kind = request.data.get('kind', 'AFTER').upper()
        if kind not in ('BEFORE', 'AFTER'):
            return Response({"error": "kind must be 'BEFORE' or 'AFTER'."}, status=status.HTTP_400_BAD_REQUEST)

        raw_file = request.FILES.get('file')
        if not raw_file:
            return Response({"error": "Image file is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Sanitize and decode image
        try:
            sanitized_img, thumbnail_img = process_and_sanitize_image(raw_file)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Parse capture metadata
        captured_at = _parse_client_timestamp(request.data.get('captured_at'))
        lat = float(request.data['lat']) if request.data.get('lat') is not None else None
        lng = float(request.data['lng']) if request.data.get('lng') is not None else None
        accuracy = float(request.data['gps_accuracy_m']) if request.data.get('gps_accuracy_m') is not None else None
        is_mock = str(request.data.get('is_mock_location', '')).lower() in ('true', '1')

        site = task.post.site
        policy = getattr(task.society.settings, 'photo_geofence_policy', 'REJECT') if hasattr(task.society, 'settings') else 'REJECT'

        allowed, rej_reason, flags, distance = validate_photo_capture_gps(
            site=site,
            captured_at=captured_at,
            lat=lat,
            lng=lng,
            gps_accuracy_m=accuracy,
            is_mock=is_mock,
            shift_start_at=task.shift_start_at,
            shift_end_at=task.shift_end_at,
            policy=policy
        )

        if not allowed:
            return Response({"error": rej_reason}, status=status.HTTP_400_BAD_REQUEST)

        photo = TaskPhoto.objects.create(
            society=task.society,
            task_instance=task,
            kind=kind,
            file=sanitized_img,
            thumbnail=thumbnail_img,
            client_uuid=client_uuid,
            captured_at=captured_at,
            gps_latitude=lat,
            gps_longitude=lng,
            gps_accuracy_m=accuracy,
            distance_from_site_m=distance,
            flags=flags,
            uploaded_by=worker
        )

        # If task was AWAITING_EVIDENCE, check if it now satisfies completion
        if task.status == 'AWAITING_EVIDENCE':
            all_photos = task.photos.all()
            has_before = all_photos.filter(kind='BEFORE').exists()
            has_after = all_photos.filter(kind='AFTER').exists()
            req = task.photo_required

            satisfied = True
            if req == 'AFTER_ONLY' and not has_after:
                satisfied = False
            elif req == 'BEFORE_AFTER' and not (has_before and has_after):
                satisfied = False

            if satisfied:
                task.status = 'DONE'
                if any(p.flags for p in all_photos):
                    task.needs_review = True
                task.save(update_fields=['status', 'needs_review', 'updated_at'])

        return Response(TaskPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/approve/
        Supervisor approves flagged task evidence so it counts as DONE in quality score.
        """
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Supervisor permissions required."}, status=status.HTTP_403_FORBIDDEN)

        task = self.get_object()
        task.needs_review = False
        task.reviewed_by = request.user
        task.reviewed_at = timezone.now()
        task.save(update_fields=['needs_review', 'reviewed_by', 'reviewed_at', 'updated_at'])

        AuditLog.objects.create(
            society=task.society,
            actor=request.user,
            action='APPROVE_TASK_EVIDENCE',
            target_model='TaskInstance',
            target_id=task.id,
            changes={'needs_review': False},
            reason=request.data.get('reason', 'Supervisor verified task completion evidence.')
        )

        return Response(TaskInstanceSerializer(task).data)

    @action(detail=True, methods=['post'], url_path='reject-evidence')
    def reject_evidence(self, request, pk=None):
        """
        POST /api/housekeeping/tasks/{id}/reject-evidence/
        Amendment 6: Supervisor rejects flagged photo evidence with reason.
        """
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Supervisor permissions required."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({"error": "Rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.needs_review = False
        task.notes = f"{task.notes}\n[EVIDENCE REJECTED by {request.user.username}]: {reason}".strip()
        task.save(update_fields=['status', 'needs_review', 'notes', 'updated_at'])

        AuditLog.objects.create(
            society=task.society,
            actor=request.user,
            action='REJECT_TASK_EVIDENCE',
            target_model='TaskInstance',
            target_id=task.id,
            changes={'status': 'IN_PROGRESS', 'needs_review': False},
            reason=reason
        )

        return Response(TaskInstanceSerializer(task).data)

    @action(detail=False, methods=['post'], url_path='excuse')
    def excuse(self, request):
        """
        POST /api/housekeeping/tasks/excuse/
        Amendment 7: Audited Supervisor excuse for a task, an area, or a whole date.
        """
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Supervisor permissions required."}, status=status.HTTP_403_FORBIDDEN)

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response({"error": "Excuse reason is required."}, status=status.HTTP_400_BAD_REQUEST)

        task_id = request.data.get('task_id')
        area_id = request.data.get('area_id')
        site_id = request.data.get('site_id')
        date_str = request.data.get('date')

        tasks_to_excuse = self.get_queryset()

        if task_id:
            tasks_to_excuse = tasks_to_excuse.filter(id=task_id)
        elif area_id and date_str:
            tasks_to_excuse = tasks_to_excuse.filter(area_id=area_id, due_date=date_str)
        elif site_id and date_str:
            tasks_to_excuse = tasks_to_excuse.filter(post__site_id=site_id, due_date=date_str)
        else:
            return Response(
                {"error": "Provide task_id, or area_id + date, or site_id + date."},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = 0
        for t in tasks_to_excuse:
            t.status = 'SKIPPED'
            t.is_excused = True
            t.skip_reason = 'EXCUSED'
            t.excused_by = request.user
            t.excuse_reason = reason
            t.save(update_fields=['status', 'is_excused', 'skip_reason', 'excused_by', 'excuse_reason', 'updated_at'])

            AuditLog.objects.create(
                society=t.society,
                actor=request.user,
                action='EXCUSE_TASK',
                target_model='TaskInstance',
                target_id=t.id,
                changes={'is_excused': True, 'skip_reason': 'EXCUSED'},
                reason=reason
            )
            updated_count += 1

        return Response({"status": "Tasks excused successfully.", "count": updated_count})


# ── 4. Prefetched Operational Board ──────────────────────────────────────────

class HousekeepingBoardView(APIView):
    """
    GET /api/housekeeping/board/?site=&date=
    Paginated, prefetched operational board grouped by post and area.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        site_id = request.query_params.get('site')
        date_str = request.query_params.get('date')
        if not site_id:
            return Response({"error": "site parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        site = get_object_or_404(Site, id=site_id)

        # Cross-society check via membership
        user = request.user
        if user.role != 'DIRECTOR':
            has_mem = Membership.objects.filter(user=user, society=site.society, is_active=True).exists()
            if not has_mem:
                raise Http404

        target_date = parse_date(date_str) if date_str else timezone.localdate()

        tasks = TaskInstance.objects.filter(
            post__site=site,
            due_date=target_date
        ).select_related(
            'post', 'shift', 'area', 'claimed_by__user', 'completed_by__user'
        ).prefetch_related('photos').order_by('post__name', 'area__name')

        is_client = user.role in ('MEMBER', 'CHAIRMAN')

        posts_data = {}
        for t in tasks:
            p_name = t.post.name
            a_name = t.area.name
            if p_name not in posts_data:
                posts_data[p_name] = {"post_id": str(t.post_id), "areas": {}}

            if a_name not in posts_data[p_name]["areas"]:
                posts_data[p_name]["areas"][a_name] = {
                    "area_id": str(t.area_id),
                    "total": 0,
                    "done": 0,
                    "pending": 0,
                    "in_progress": 0,
                    "awaiting_evidence": 0,
                    "missed": 0,
                    "skipped": 0,
                    "needs_review": 0,
                    "tasks": []
                }

            sec = posts_data[p_name]["areas"][a_name]
            sec["total"] += 1
            if t.status == 'DONE':
                sec["done"] += 1
            elif t.status == 'PENDING':
                sec["pending"] += 1
            elif t.status == 'IN_PROGRESS':
                sec["in_progress"] += 1
            elif t.status == 'AWAITING_EVIDENCE':
                sec["awaiting_evidence"] += 1
            elif t.status == 'MISSED':
                sec["missed"] += 1
            elif t.status == 'SKIPPED':
                sec["skipped"] += 1

            if t.needs_review:
                sec["needs_review"] += 1

            # Clients receive summary without raw task photos or worker PII
            t_data = {
                "id": str(t.id),
                "name": t.name,
                "status": t.status,
                "photo_required": t.photo_required,
                "needs_review": t.needs_review
            }
            if not is_client:
                t_data["claimed_by"] = t.claimed_by.user.get_full_name() if t.claimed_by else None
                t_data["completed_by"] = t.completed_by.user.get_full_name() if t.completed_by else None
                t_data["photos"] = TaskPhotoSerializer(t.photos.all(), many=True).data

            sec["tasks"].append(t_data)

        # Calculate completion %
        for p_info in posts_data.values():
            for a_info in p_info["areas"].values():
                tot = a_info["total"]
                dn = a_info["done"]
                a_info["completion_pct"] = round((dn / tot * 100), 1) if tot > 0 else 100.0

        return Response({
            "site_id": str(site.id),
            "site_name": site.name,
            "date": target_date.isoformat(),
            "posts": posts_data
        })


# ── 5. Inspection ViewSet ────────────────────────────────────────────────────

class InspectionViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    Quality inspections performed by Supervisors or Directors.
    Creates rework TaskInstance if score is 1-3 (FAILED or NEEDS_REWORK).
    """
    queryset = Inspection.objects.select_related('society', 'post', 'area', 'inspector').prefetch_related('photos')
    serializer_class = InspectionSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOpsUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        post = serializer.validated_data.get('post')
        society = (post.society if post else None) or self.resolve_create_society(self.request)
        inspection = serializer.save(society=society, inspector=self.request.user)

        # If FAILED or NEEDS_REWORK: generate rework task
        if inspection.status in ('FAILED', 'NEEDS_REWORK'):
            shift = inspection.post.shifts.first()
            if shift:
                start_dt = timezone.now()
                end_dt = start_dt + timedelta(hours=4)
                TaskInstance.objects.create(
                    society=society,
                    post=inspection.post,
                    shift=shift,
                    area=inspection.area or inspection.post.site.areas.first(),
                    name=f"Rework: {inspection.notes or 'Quality remediation'}",
                    photo_required='BEFORE_AFTER',
                    estimated_minutes=45,
                    due_date=inspection.date,
                    shift_start_at=start_dt,
                    shift_end_at=end_dt,
                    is_rework=True,
                    status='PENDING'
                )

        AuditLog.objects.create(
            society=society,
            actor=self.request.user,
            action='CONDUCT_INSPECTION',
            target_model='Inspection',
            target_id=inspection.id,
            changes=_to_json_safe(serializer.data),
            reason=f"Inspection completed with score {inspection.score}/5"
        )


# ── 6. Complaint ViewSet ─────────────────────────────────────────────────────

class ComplaintViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    """
    Resident complaints lifecycle.
    Throttled creation. Reopened count tracked. Client confirmation required.
    """
    queryset = Complaint.objects.select_related('society', 'site', 'post', 'area', 'raised_by', 'assigned_to')
    serializer_class = ComplaintSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'complaint_create'

    def perform_create(self, serializer):
        site = serializer.validated_data.get('site')
        post = serializer.validated_data.get('post')
        society = (site.society if site else None) or (post.society if post else None) or self.resolve_create_society(self.request)

        # Amendment 8: raised_by needs active approved membership
        if self.request.user.role != 'DIRECTOR':
            has_mem = Membership.objects.filter(user=self.request.user, society=society, is_active=True).exists()
            if not has_mem:
                raise ValidationError({"raised_by": "You must have an active membership in this society to raise a complaint."})

        raw_photo = self.request.FILES.get('photo')
        sanitized_photo = None
        if raw_photo:
            sanitized_photo, _ = process_and_sanitize_image(raw_photo)

        complaint = serializer.save(
            society=society,
            raised_by=self.request.user,
            photo=sanitized_photo
        )

        AuditLog.objects.create(
            society=society,
            actor=self.request.user,
            action='RAISE_COMPLAINT',
            target_model='Complaint',
            target_id=complaint.id,
            changes=_to_json_safe(serializer.data),
            reason='Complaint submitted by resident'
        )

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """
        POST /api/housekeeping/complaints/{id}/confirm/
        Client confirms resolution or disputes/rejects it (reopening complaint).
        """
        complaint = self.get_object()
        confirmed = str(request.data.get('confirmed', '')).lower() in ('true', '1')
        notes = request.data.get('rejection_notes', '').strip()

        if confirmed:
            complaint.client_confirmed = True
            complaint.save(update_fields=['client_confirmed', 'updated_at'])
        else:
            complaint.client_confirmed = False
            complaint.status = 'OPEN'
            complaint.reopened_count += 1
            complaint.disputed_by_client = True
            complaint.dispute_notes = notes
            complaint.save(update_fields=['client_confirmed', 'status', 'reopened_count', 'disputed_by_client', 'dispute_notes', 'updated_at'])

        return Response(ComplaintSerializer(complaint).data)


# ── 7. Supply Item & Request ViewSets ────────────────────────────────────────

class SupplyItemViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = SupplyItem.objects.select_related('society')
    serializer_class = SupplyItemSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsOpsUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        society = self.resolve_create_society(self.request)
        serializer.save(society=society)


class SupplyRequestViewSet(SocietyScopedMixin, viewsets.ModelViewSet):
    queryset = SupplyRequest.objects.select_related('society', 'item', 'requested_by__user', 'reviewed_by')
    serializer_class = SupplyRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'supply_request_create'

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', '') == 'WORKER':
            return SupplyRequest.objects.filter(requested_by__user=user)
        return super().get_queryset()

    def perform_create(self, serializer):
        worker = getattr(self.request.user, 'worker_profile', None)
        if not worker:
            raise ValidationError({"requested_by": "Only registered workers can submit supply requests."})
        item = serializer.validated_data.get('item')
        society = (item.society if item else None) or self.resolve_create_society(self.request)
        serializer.save(society=society, requested_by=worker)

    def perform_create(self, serializer):
        worker = getattr(self.request.user, 'worker_profile', None)
        if not worker:
            raise ValidationError({"requested_by": "Only registered workers can submit supply requests."})
        society = self.resolve_create_society(self.request)
        serializer.save(society=society, requested_by=worker)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Supervisor permissions required."}, status=status.HTTP_403_FORBIDDEN)
        req = self.get_object()
        req.status = 'APPROVED'
        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        return Response(SupplyRequestSerializer(req).data)

    @action(detail=True, methods=['post'], url_path='issue')
    def issue(self, request, pk=None):
        if request.user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response({"error": "Supervisor permissions required."}, status=status.HTTP_403_FORBIDDEN)
        req = self.get_object()
        req.status = 'ISSUED'
        req.save(update_fields=['status', 'updated_at'])
        return Response(SupplyRequestSerializer(req).data)


# ── 8. Quality Score Endpoint ────────────────────────────────────────────────

class QualityScoreView(APIView):
    """
    GET /api/housekeeping/quality-score/?site=&month=YYYY-MM
    Amendment 11: Allowed for Client roles, Supervisors and Director only.
    Workers are blocked with 403 Forbidden.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role == 'WORKER':
            return Response({"error": "Workers are not authorized to view quality scores."}, status=status.HTTP_403_FORBIDDEN)

        site_id = request.query_params.get('site')
        month_str = request.query_params.get('month')  # 'YYYY-MM'

        if not site_id:
            return Response({"error": "site is required."}, status=status.HTTP_400_BAD_REQUEST)

        site = get_object_or_404(Site, id=site_id)

        # Cross-society check
        if request.user.role != 'DIRECTOR':
            has_mem = Membership.objects.filter(user=request.user, society=site.society, is_active=True).exists()
            if not has_mem:
                raise Http404

        now = timezone.now()
        if month_str:
            try:
                parts = month_str.split('-')
                year = int(parts[0])
                month = int(parts[1])
            except Exception:
                return Response({"error": "Invalid month format. Expected YYYY-MM."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            year = now.year
            month = now.month

        # Closed month -> retrieve or create immutable snapshot
        is_past_month = (year < now.year) or (year == now.year and month < now.month)
        if is_past_month:
            snapshot = create_or_get_quality_score_snapshot(site, year, month, request.user)
            return Response(QualityScoreSnapshotSerializer(snapshot).data)

        # Current month -> live calculation
        calc = calculate_monthly_quality_score(site, year, month)
        return Response(calc)


# ── 9. Private Photo Download View ───────────────────────────────────────────

class PhotoFileDownloadView(APIView):
    """
    GET /api/housekeeping/photos/{id}/file/?thumb=1
    Permission-checked photo delivery.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        photo = get_object_or_404(TaskPhoto.objects.select_related('society', 'task_instance', 'uploaded_by'), id=pk)
        user = request.user

        # 1. Cross-society 404
        if user.role != 'DIRECTOR':
            has_mem = Membership.objects.filter(user=user, society=photo.society, is_active=True).exists()
            worker = getattr(user, 'worker_profile', None)
            is_own_worker = (worker and photo.uploaded_by_id == worker.id)
            if not (has_mem or is_own_worker):
                raise Http404

        # 2. Role privacy checks
        if user.role in ('MEMBER', 'CHAIRMAN'):
            return Response(
                {"error": "Residents and Chairmen cannot view raw housekeeping task photos."},
                status=status.HTTP_403_FORBIDDEN
            )

        if user.role == 'WORKER':
            worker = getattr(user, 'worker_profile', None)
            if not worker or photo.uploaded_by_id != worker.id:
                return Response({"error": "You can only view your own task photos."}, status=status.HTTP_403_FORBIDDEN)

        # Serve thumbnail or full file
        is_thumb = request.query_params.get('thumb') == '1'
        target_file = photo.thumbnail if (is_thumb and photo.thumbnail) else photo.file

        if not target_file:
            raise Http404

        try:
            url = target_file.url
            if url.startswith('http'):
                return HttpResponseRedirect(url)
            return HttpResponse(target_file.read(), content_type="image/jpeg")
        except Exception:
            return HttpResponse(target_file.read(), content_type="image/jpeg")

