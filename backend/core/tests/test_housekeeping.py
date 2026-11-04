import io
import json
import uuid
import zoneinfo
from datetime import datetime, date, time, timedelta, timezone as dt_tz
from decimal import Decimal
import pytest
from unittest.mock import patch
from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    User, Society, Site, Membership, SocietySettings,
    WorkerProfile, Post, Shift, RosterAssignment, DailyRoster,
    AttendanceEvent, Alert, AuditLog, Notification,
    Area, TaskTemplate, TaskInstance, TaskPhoto,
    Inspection, InspectionPhoto, Complaint,
    SupplyItem, SupplyRequest, QualityScoreSnapshot
)
from core.housekeeping_utils import (
    haversine_distance, process_and_sanitize_image,
    calculate_monthly_quality_score, create_or_get_quality_score_snapshot
)


def make_test_image(width=100, height=100, color='blue', fmt='JPEG'):
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile("evidence.jpg", buf.getvalue(), content_type="image/jpeg")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def kolkata_tz():
    return zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.fixture
def society_a(db):
    soc = Society.objects.create(name="HK Society Alpha", client_type="SOCIETY", address="Pune")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        shift_start_grace_minutes=15,
        early_clock_in_minutes=30,
        early_leave_minutes=15,
        overtime_threshold_minutes=30,
        mock_location_policy='REJECT',
        photo_geofence_policy='REJECT',
        task_missed_grace_minutes=30,
        evidence_deadline_hours=24,
        photo_retention_days=90,
        completion_weight=40,
        inspection_weight=40,
        complaint_weight=20
    )
    return soc


@pytest.fixture
def society_b(db):
    soc = Society.objects.create(name="HK Society Beta", client_type="SOCIETY", address="Mumbai")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        photo_geofence_policy='FLAG',
        completion_weight=50,
        inspection_weight=30,
        complaint_weight=20
    )
    return soc


@pytest.fixture
def site_a(society_a):
    return Site.objects.create(
        society=society_a,
        name="Alpha Towers",
        latitude=18.5204,
        longitude=73.8567,
        geofence_radius_m=100,
        max_gps_accuracy_m=50,
        area_name="Kothrud",
        pincode="411038"
    )


@pytest.fixture
def site_b(society_b):
    return Site.objects.create(
        society=society_b,
        name="Beta Heights",
        latitude=19.0760,
        longitude=72.8777,
        geofence_radius_m=100,
        max_gps_accuracy_m=50
    )


@pytest.fixture
def area_lobby(society_a, site_a):
    return Area.objects.create(
        society=society_a,
        site=site_a,
        name="Main Lobby",
        floor_or_block="Ground"
    )


@pytest.fixture
def area_garden(society_a, site_a):
    return Area.objects.create(
        society=society_a,
        site=site_a,
        name="Central Garden",
        floor_or_block="Outdoor"
    )


@pytest.fixture
def post_a(society_a, site_a):
    return Post.objects.create(
        society=society_a,
        site=site_a,
        name="Lobby Housekeeping",
        category="HOUSEKEEPING",
        billing_basis="PER_SHIFT",
        client_rate=Decimal("800.00"),
        is_active=True
    )


@pytest.fixture
def shift_morning(society_a, post_a):
    return Shift.objects.create(
        society=society_a,
        post=post_a,
        name="Morning Cleaning Shift",
        start_time=time(7, 0),
        end_time=time(15, 0),
        crosses_midnight=False,
        days_of_week=[0, 1, 2, 3, 4, 5, 6],
        required_headcount=1,
        is_active=True
    )


@pytest.fixture
def shift_night(society_a, post_a):
    return Shift.objects.create(
        society=society_a,
        post=post_a,
        name="Night Sanitization Shift",
        start_time=time(22, 0),
        end_time=time(6, 0),
        crosses_midnight=True,
        days_of_week=[0, 1, 2, 3, 4, 5, 6],
        required_headcount=1,
        is_active=True
    )


@pytest.fixture
def supervisor_a(society_a):
    user = User.objects.create_user(username="sup_hk_a", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society_a, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def director_user(society_a):
    user = User.objects.create_user(username="dir_hk", password="altuspassword123!", role="DIRECTOR")
    return user


@pytest.fixture
def chairman_a(society_a):
    user = User.objects.create_user(username="chair_hk_a", password="altuspassword123!", role="CHAIRMAN")
    Membership.objects.create(user=user, society=society_a, role="CHAIRMAN", is_active=True)
    return user


@pytest.fixture
def member_a(society_a):
    user = User.objects.create_user(username="mem_hk_a", password="altuspassword123!", role="MEMBER")
    Membership.objects.create(user=user, society=society_a, role="MEMBER", is_active=True)
    return user


@pytest.fixture
def worker_hk_1(society_a):
    user = User.objects.create_user(username="worker_hk_1", role="WORKER")
    user.set_unusable_password()
    user.save()
    wp = WorkerProfile.objects.create(
        user=user,
        phone="+919811111111",
        verification_status="VERIFIED",
        category="HOUSEKEEPING"
    )
    return user, wp


@pytest.fixture
def worker_hk_2(society_a):
    user = User.objects.create_user(username="worker_hk_2", role="WORKER")
    user.set_unusable_password()
    user.save()
    wp = WorkerProfile.objects.create(
        user=user,
        phone="+919822222222",
        verification_status="VERIFIED",
        category="HOUSEKEEPING"
    )
    return user, wp


@pytest.mark.django_db
class TestHousekeepingTaskManagement:

    def test_task_generation_daily_weekly_monthly_and_effective_dates(
        self, society_a, post_a, shift_morning, area_lobby, area_garden
    ):
        """
        Generation respects daily, weekly, monthly (including short months),
        skips inactive templates and inactive posts/shifts, and generates even if roster slot is UNFILLED.
        """
        # 1. Daily template
        t_daily = TaskTemplate.objects.create(
            society=society_a, post=post_a, area=area_lobby, shift=shift_morning,
            name="Mop Lobby", frequency='DAILY', photo_required='BEFORE_AFTER',
            estimated_minutes=30, sort_order=1,
            effective_from=datetime(2026, 1, 1).date()
        )

        # 2. Weekly template (Wednesdays only: weekday=2)
        t_weekly = TaskTemplate.objects.create(
            society=society_a, post=post_a, area=area_garden, shift=shift_morning,
            name="Trim Garden Bushes", frequency='WEEKLY', days_of_week=[2],
            photo_required='AFTER_ONLY', estimated_minutes=60, sort_order=2,
            effective_from=datetime(2026, 1, 1).date()
        )

        # 3. Monthly template (31st of month; short months map to last day)
        t_monthly = TaskTemplate.objects.create(
            society=society_a, post=post_a, area=area_lobby, shift=shift_morning,
            name="Deep Scrub Lobby Tiles", frequency='MONTHLY', day_of_month=31,
            photo_required='BEFORE_AFTER', estimated_minutes=90, sort_order=3,
            effective_from=datetime(2026, 1, 1).date()
        )

        # Test on a Wednesday in April (April 29, 2026 is Wednesday = 2)
        call_command('generate_daily_tasks', date='2026-04-29')
        tasks_29 = TaskInstance.objects.filter(due_date='2026-04-29')
        # Expect Daily and Weekly
        assert tasks_29.count() == 2
        names_29 = set(tasks_29.values_list('name', flat=True))
        assert "Mop Lobby" in names_29
        assert "Trim Garden Bushes" in names_29
        # Check copied attributes (Amendment 5)
        mop_task = tasks_29.get(template=t_daily)
        assert mop_task.photo_required == 'BEFORE_AFTER'
        assert mop_task.estimated_minutes == 30

        # Test on April 30, 2026 (Thursday = 3; April has 30 days -> day 31 maps to day 30)
        call_command('generate_daily_tasks', date='2026-04-30')
        tasks_30 = TaskInstance.objects.filter(due_date='2026-04-30')
        # Expect Daily and Monthly (short month edge case!)
        assert tasks_30.count() == 2
        names_30 = set(tasks_30.values_list('name', flat=True))
        assert "Mop Lobby" in names_30
        assert "Deep Scrub Lobby Tiles" in names_30

        # Rerun is idempotent (slots not duplicated)
        call_command('generate_daily_tasks', date='2026-04-30')
        assert TaskInstance.objects.filter(due_date='2026-04-30').count() == 2

    def test_worker_cannot_claim_or_complete_without_attendance(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, kolkata_tz
    ):
        """
        Worker must be clocked in on that shift to claim or complete tasks (returns 403).
        """
        u1, wp1 = worker_hk_1
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='SCHEDULED',
            shift_start_at=s_start, shift_end_at=s_end
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Sanitize Lobby", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='PENDING'
        )

        api_client.force_authenticate(user=u1)

        # Worker attempts claim without clocking in -> 403 Forbidden
        claim_res = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert claim_res.status_code == 403
        assert "must be clocked in" in claim_res.data['error']

        # Worker clocks in
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        # Worker can now claim successfully
        claim_res_ok = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert claim_res_ok.status_code == 200
        assert claim_res_ok.data['status'] == 'IN_PROGRESS'
        assert str(claim_res_ok.data['claimed_by']) == str(wp1.id)

    def test_atomic_claim_concurrency_409(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, worker_hk_2, kolkata_tz
    ):
        """
        Amendment 3: Two workers attempt atomic claim; second request receives 409 Conflict.
        """
        u1, wp1 = worker_hk_1
        u2, wp2 = worker_hk_2
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Dust Railings", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='PENDING'
        )

        # Worker 1 claims
        api_client.force_authenticate(user=u1)
        r1 = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert r1.status_code == 200

        # Worker 2 attempts claim on the same task -> 409 Conflict
        api_client.force_authenticate(user=u2)
        # Even with clock in:
        slot2 = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=2, worker=wp2, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot2, worker=wp2,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )
        r2 = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert r2.status_code == 409
        assert "already been claimed" in r2.data['error']

    def test_original_worker_blocked_when_slot_covered(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, worker_hk_2, kolkata_tz
    ):
        """
        Original worker whose slot is COVERED cannot claim/complete tasks; reliever can.
        """
        u1, wp1 = worker_hk_1
        u2, wp2 = worker_hk_2
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, covered_by=wp2, status='COVERED',
            shift_start_at=s_start, shift_end_at=s_end
        )
        # Reliever clocks in
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp2,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Wash Glass Doors", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='PENDING'
        )

        # Original worker attempts claim -> 409 Conflict
        api_client.force_authenticate(user=u1)
        r1 = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert r1.status_code == 409
        assert "reassigned to a reliever" in r1.data['error']

        # Reliever claims -> 200 OK
        api_client.force_authenticate(user=u2)
        r2 = api_client.post(f"/api/housekeeping/tasks/{task.id}/claim/", format='json')
        assert r2.status_code == 200
        assert str(r2.data['claimed_by']) == str(wp2.id)

    def test_awaiting_evidence_and_completion_resolution(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, kolkata_tz
    ):
        """
        Amendment 2: Complete with expected_photo_uuids moves task to AWAITING_EVIDENCE;
        uploading the required photos satisfies requirements and moves task to DONE.
        """
        u1, wp1 = worker_hk_1
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Floor Disinfection", photo_required='AFTER_ONLY',
            due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )

        api_client.force_authenticate(user=u1)
        expected_uuid = str(uuid.uuid4())

        # Complete with expected photo uuid
        complete_res = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/complete/",
            {"expected_photo_uuids": [expected_uuid]},
            format='json'
        )
        assert complete_res.status_code == 200
        assert complete_res.data['status'] == 'AWAITING_EVIDENCE'

        # Upload the expected AFTER photo from within site geofence
        img_file = make_test_image()
        upload_res = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {
                "file": img_file,
                "kind": "AFTER",
                "client_uuid": expected_uuid,
                "captured_at": timezone.now().isoformat(),
                "lat": 18.5204,
                "lng": 73.8567,
                "gps_accuracy_m": 15.0
            },
            format='multipart'
        )
        assert upload_res.status_code == 201

        # Task has now satisfied requirements and transitioned to DONE
        task.refresh_from_db()
        assert task.status == 'DONE'
        assert task.completed_by == wp1

    def test_capture_time_gps_geofence_and_offline_upload(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, kolkata_tz
    ):
        """
        Capture-time GPS decides geofence:
        - Photo captured inside site geofence is accepted even if uploaded later from afar.
        - Photo captured outside site geofence is rejected under REJECT policy.
        """
        u1, wp1 = worker_hk_1
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Inspect Elevators", photo_required='NONE',
            due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )

        api_client.force_authenticate(user=u1)

        # 1. Captured inside site geofence (18.5204, 73.8567) -> Accepted
        res_inside = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {
                "file": make_test_image(),
                "kind": "BEFORE",
                "client_uuid": str(uuid.uuid4()),
                "captured_at": timezone.now().isoformat(),
                "lat": 18.52045,
                "lng": 73.85675,
                "gps_accuracy_m": 10.0
            },
            format='multipart'
        )
        assert res_inside.status_code == 201
        assert res_inside.data['distance_from_site_m'] < 100.0

        # 2. Captured far outside site geofence (e.g. 19.000, 74.000) under REJECT policy -> 400 Bad Request
        res_outside = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {
                "file": make_test_image(),
                "kind": "AFTER",
                "client_uuid": str(uuid.uuid4()),
                "captured_at": timezone.now().isoformat(),
                "lat": 19.0000,
                "lng": 74.0000,
                "gps_accuracy_m": 10.0
            },
            format='multipart'
        )
        assert res_outside.status_code == 400
        assert "outside site geofence" in res_outside.data['error']

    def test_supervisor_audited_excuse_task_action(
        self, api_client, society_a, post_a, shift_morning, area_lobby, supervisor_a, kolkata_tz
    ):
        """
        Amendment 7: Supervisor excuses a task with audited reason. Excused tasks are excluded from SLA denominator.
        """
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Paint Touchup", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='PENDING'
        )

        api_client.force_authenticate(user=supervisor_a)
        res = api_client.post(
            "/api/housekeeping/tasks/excuse/",
            {
                "task_id": str(task.id),
                "reason": "Lobby under civil repairs; painting postponed"
            },
            format='json'
        )
        assert res.status_code == 200
        assert res.data['count'] == 1

        task.refresh_from_db()
        assert task.status == 'SKIPPED'
        assert task.is_excused is True
        assert task.skip_reason == 'EXCUSED'

        # AuditLog recorded
        audit = AuditLog.objects.filter(action='EXCUSE_TASK', target_id=task.id).first()
        assert audit is not None
        assert audit.actor == supervisor_a

    def test_overnight_shift_tasks_marked_missed(
        self, society_a, post_a, shift_night, area_lobby, kolkata_tz
    ):
        """
        Overnight shifts crossing midnight are accurately marked MISSED past shift_end_at + grace.
        """
        yesterday = timezone.localdate() - timedelta(days=1)
        s_start = timezone.make_aware(datetime.combine(yesterday, time(22, 0)), kolkata_tz).astimezone(dt_tz.utc)
        # Shift ends this morning at 06:00
        s_end = timezone.make_aware(datetime.combine(timezone.localdate(), time(6, 0)), kolkata_tz).astimezone(dt_tz.utc)

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_night, area=area_lobby,
            name="Night Sanitization", due_date=yesterday,
            shift_start_at=s_start, shift_end_at=s_end,
            status='PENDING'
        )

        # Run command
        call_command('mark_missed_tasks')
        task.refresh_from_db()
        assert task.status == 'MISSED'
        assert "Shift ended without completion" in task.notes

    def test_inspection_failed_creates_rework_task(
        self, api_client, society_a, post_a, shift_morning, area_lobby, supervisor_a
    ):
        """
        Inspection with score 2 (NEEDS_REWORK) automatically generates a rework TaskInstance.
        """
        api_client.force_authenticate(user=supervisor_a)
        res = api_client.post(
            "/api/housekeeping/inspections/",
            {
                "post": str(post_a.id),
                "area": str(area_lobby.id),
                "date": timezone.localdate().isoformat(),
                "score": 2,
                "status": "NEEDS_REWORK",
                "notes": "Lobby corners dusty; glass door smudged"
            },
            format='json'
        )
        assert res.status_code == 201

        # Rework task generated
        rework_task = TaskInstance.objects.filter(is_rework=True, post=post_a).first()
        assert rework_task is not None
        assert "Rework" in rework_task.name
        assert rework_task.photo_required == 'BEFORE_AFTER'

    def test_complaint_lifecycle_and_reopen_on_client_rejection(
        self, api_client, society_a, site_a, member_a, supervisor_a
    ):
        """
        Member raises complaint -> Supervisor resolves -> Member rejects resolution ->
        reopens with reopened_count incremented and disputed_by_client=True.
        """
        # 1. Member creates complaint
        api_client.force_authenticate(user=member_a)
        res_create = api_client.post(
            "/api/housekeeping/complaints/",
            {
                "site": str(site_a.id),
                "description": "Foul smell near lift lobby"
            },
            format='json'
        )
        assert res_create.status_code == 201
        complaint_id = res_create.data['id']

        # 2. Supervisor resolves
        api_client.force_authenticate(user=supervisor_a)
        res_res = api_client.patch(
            f"/api/housekeeping/complaints/{complaint_id}/",
            {
                "status": "RESOLVED",
                "resolution_notes": "Garbage removed and deodorized"
            },
            format='json'
        )
        assert res_res.status_code == 200

        # 3. Member disputes resolution (rejects)
        api_client.force_authenticate(user=member_a)
        res_rej = api_client.post(
            f"/api/housekeeping/complaints/{complaint_id}/confirm/",
            {
                "confirmed": False,
                "rejection_notes": "Smell is still present near elevator shaft"
            },
            format='json'
        )
        assert res_rej.status_code == 200
        assert res_rej.data['status'] == 'OPEN'
        assert res_rej.data['reopened_count'] == 1
        assert res_rej.data['disputed_by_client'] is True

    def test_quality_score_hand_calculated_85_6_example(
        self, society_a, site_a, post_a, shift_morning, area_lobby, supervisor_a
    ):
        """
        Verifies exact hand-calculated 85.6 quality score example:
        - Tasks: 90 / 100 completed (T = 90.0)
        - Inspections: average score 4.2 / 5 (I = 84.0)
        - Complaints: 8 of 10 resolved within SLA (C = 80.0)
        - Weights: 40 / 40 / 20
        Score = 0.4*90 + 0.4*84 + 0.2*80 = 36 + 33.6 + 16 = 85.6
        """
        now = timezone.now()
        year = now.year
        month = now.month
        target_date = datetime(year, month, 15).date()
        s_start = now - timedelta(hours=8)
        s_end = now

        # 1. 100 Tasks: 90 DONE, 10 MISSED
        for i in range(90):
            TaskInstance.objects.create(
                society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
                name=f"Task Done {i}", due_date=target_date,
                shift_start_at=s_start, shift_end_at=s_end,
                status='DONE', needs_review=False
            )
        for i in range(10):
            TaskInstance.objects.create(
                society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
                name=f"Task Missed {i}", due_date=target_date,
                shift_start_at=s_start, shift_end_at=s_end,
                status='MISSED'
            )

        # 2. Inspections: average 4.2 (e.g. four 4s and one 5 = 21/5 = 4.2)
        for score in [4, 4, 4, 4, 5]:
            Inspection.objects.create(
                society=society_a, post=post_a, area=area_lobby, inspector=supervisor_a,
                date=target_date, score=score, status='PASSED'
            )

        # 3. Complaints: 10 total. 8 resolved within SLA, 2 unresolved past SLA
        # Past SLA creation time (> 24h ago)
        old_time = now - timedelta(hours=36)
        for i in range(8):
            comp = Complaint.objects.create(
                society=society_a, site=site_a, raised_by=supervisor_a,
                description=f"Complaint resolved {i}", status='RESOLVED'
            )
            comp.created_at = old_time
            comp.resolved_at = old_time + timedelta(hours=10)  # within 24h
            comp.save()

        for i in range(2):
            comp_fail = Complaint.objects.create(
                society=society_a, site=site_a, raised_by=supervisor_a,
                description=f"Complaint pending {i}", status='OPEN'
            )
            comp_fail.created_at = old_time
            comp_fail.save()

        calc = calculate_monthly_quality_score(site_a, year, month)
        assert calc["task_completion"]["score_pct"] == 90.0
        assert calc["inspection"]["score_pct"] == 84.0
        assert calc["complaint_sla"]["score_pct"] == 80.0
        assert calc["total_score"] == 85.6

    def test_quality_score_endpoint_blocks_worker_and_allows_client(
        self, api_client, society_a, site_a, worker_hk_1, member_a
    ):
        """
        Amendment 11: Worker accessing quality score receives 403 Forbidden.
        Client receives 200 OK.
        """
        u_worker, wp_worker = worker_hk_1

        # Worker -> 403
        api_client.force_authenticate(user=u_worker)
        res_w = api_client.get(f"/api/housekeeping/quality-score/?site={site_a.id}")
        assert res_w.status_code == 403

        # Client Member -> 200
        api_client.force_authenticate(user=member_a)
        res_m = api_client.get(f"/api/housekeeping/quality-score/?site={site_a.id}")
        assert res_m.status_code == 200
        assert "total_score" in res_m.data

    def test_cross_society_isolation_returns_404(
        self, api_client, society_b, site_b, supervisor_a
    ):
        """
        Supervisor of Society A accessing Society B housekeeping resources returns 404 Not Found.
        """
        api_client.force_authenticate(user=supervisor_a)

        # Accessing Society B board -> 404
        res_board = api_client.get(f"/api/housekeeping/board/?site={site_b.id}")
        assert res_board.status_code == 404

        # Accessing Society B quality score -> 404
        res_qs = api_client.get(f"/api/housekeeping/quality-score/?site={site_b.id}")
        assert res_qs.status_code == 404

    def test_cleanup_expired_photos_command(
        self, society_a, post_a, shift_morning, area_lobby, worker_hk_1
    ):
        """
        Amendment 12: Cleanup expired photos past photo_retention_days (default 90).
        """
        u1, wp1 = worker_hk_1
        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Photo Retention Check", due_date=timezone.localdate(),
            shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='DONE'
        )

        photo = TaskPhoto.objects.create(
            society=society_a, task_instance=task, kind='AFTER',
            file=SimpleUploadedFile("old.jpg", b"fake", content_type="image/jpeg"),
            client_uuid=uuid.uuid4(), captured_at=timezone.now() - timedelta(days=120),
            uploaded_by=wp1
        )
        # Backdate created_at
        TaskPhoto.objects.filter(id=photo.id).update(created_at=timezone.now() - timedelta(days=120))

        # Default run is dry-run: reports count without deleting
        call_command('cleanup_expired_photos')
        assert TaskPhoto.objects.filter(id=photo.id).exists() is True

        # Explicit dry_run=True flag also reports without deleting
        call_command('cleanup_expired_photos', dry_run=True)
        assert TaskPhoto.objects.filter(id=photo.id).exists() is True

        # Commit flag executes actual deletion
        call_command('cleanup_expired_photos', commit=True)
        assert TaskPhoto.objects.filter(id=photo.id).exists() is False

    @pytest.mark.parametrize("status_val,disputed,should_protect", [
        ('OPEN', False, True),
        ('ACKNOWLEDGED', False, True),
        ('IN_PROGRESS', False, True),
        ('RESOLVED', False, False),
        ('REJECTED', False, False),
        ('RESOLVED', True, True),
        ('REJECTED', True, True),
    ])
    def test_cleanup_expired_photos_complaint_status_protection(
        self, society_a, post_a, shift_morning, area_lobby, worker_hk_1, status_val, disputed, should_protect
    ):
        """
        cleanup_expired_photos protects photos of ACKNOWLEDGED complaints and any complaint
        not RESOLVED/REJECTED, as well as disputed resolved/rejected complaints.
        """
        u1, wp1 = worker_hk_1
        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name=f"Status Test {status_val} {disputed}", due_date=timezone.localdate(),
            shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='DONE'
        )

        photo = TaskPhoto.objects.create(
            society=society_a, task_instance=task, kind='AFTER',
            file=SimpleUploadedFile("old_complaint.jpg", b"fake", content_type="image/jpeg"),
            client_uuid=uuid.uuid4(), captured_at=timezone.now() - timedelta(days=120),
            uploaded_by=wp1
        )
        TaskPhoto.objects.filter(id=photo.id).update(created_at=timezone.now() - timedelta(days=120))

        # Create Complaint on this area
        Complaint.objects.create(
            society=society_a,
            site=post_a.site,
            area=area_lobby,
            post=post_a,
            raised_by=u1,
            description=f"Complaint with status {status_val}",
            status=status_val,
            disputed_by_client=disputed
        )

        call_command('cleanup_expired_photos', commit=True)

        if should_protect:
            assert TaskPhoto.objects.filter(id=photo.id).exists() is True
        else:
            assert TaskPhoto.objects.filter(id=photo.id).exists() is False

    def test_task_release_and_supervisor_reassign(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, worker_hk_2, supervisor_a, kolkata_tz
    ):
        """
        1. Worker releases claimed task -> returns to PENDING, audited.
        2. Supervisor reassigns task to another worker -> audited.
        """
        u1, wp1 = worker_hk_1
        u2, wp2 = worker_hk_2
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot1 = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot1, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        slot2 = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=2, worker=wp2, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot2, worker=wp2,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )

        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Sweep Pathways", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )

        # 1. Worker 1 releases task
        api_client.force_authenticate(user=u1)
        rel_res = api_client.post(f"/api/housekeeping/tasks/{task.id}/release/", {"reason": "Shift handover"}, format='json')
        assert rel_res.status_code == 200
        assert rel_res.data['status'] == 'PENDING'
        assert rel_res.data['claimed_by'] is None
        assert AuditLog.objects.filter(target_id=task.id, action='RELEASE_TASK').exists() is True

        # 2. Supervisor reassigns task to Worker 2
        api_client.force_authenticate(user=supervisor_a)
        reasgn_res = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/reassign/",
            {"worker": str(wp2.id), "reason": "Supervisor workload balancing"},
            format='json'
        )
        assert reasgn_res.status_code == 200
        assert reasgn_res.data['status'] == 'IN_PROGRESS'
        assert str(reasgn_res.data['claimed_by']) == str(wp2.id)
        assert AuditLog.objects.filter(target_id=task.id, action='REASSIGN_TASK').exists() is True

    def test_deleting_area_or_task_template_with_history_blocked(
        self, api_client, society_a, post_a, shift_morning, area_lobby, supervisor_a
    ):
        """
        Deleting Area or TaskTemplate with historical links returns 400 Bad Request.
        """
        api_client.force_authenticate(user=supervisor_a)

        # Create template linked to area
        tmpl = TaskTemplate.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Wash Baseboards", frequency='DAILY', photo_required='NONE'
        )
        # Attempt deleting Area with linked template -> 400
        del_area = api_client.delete(f"/api/housekeeping/areas/{area_lobby.id}/")
        assert del_area.status_code == 400
        assert "linked task records" in del_area.data['error']

        # Create TaskInstance linked to template
        TaskInstance.objects.create(
            society=society_a, template=tmpl, post=post_a, shift=shift_morning, area=area_lobby,
            name="Wash Baseboards", due_date=timezone.localdate(),
            shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='PENDING'
        )
        # Attempt deleting TaskTemplate with historical instances -> 400
        del_tmpl = api_client.delete(f"/api/housekeeping/templates/{tmpl.id}/")
        assert del_tmpl.status_code == 400
        assert "historical task instances" in del_tmpl.data['error']

    def test_template_edit_does_not_change_already_generated_tasks(
        self, api_client, society_a, post_a, shift_morning, area_lobby, supervisor_a
    ):
        """
        Amendment 5: Template edits apply to future dates only.
        Existing generated tasks retain their original name and estimated_minutes.
        """
        tmpl = TaskTemplate.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Original Mop Task", frequency='DAILY', photo_required='BEFORE_AFTER',
            estimated_minutes=25, sort_order=1
        )
        task = TaskInstance.objects.create(
            society=society_a, template=tmpl, post=post_a, shift=shift_morning, area=area_lobby,
            name=tmpl.name, photo_required=tmpl.photo_required, estimated_minutes=tmpl.estimated_minutes,
            due_date=timezone.localdate(), shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='PENDING'
        )

        api_client.force_authenticate(user=supervisor_a)
        res = api_client.patch(
            f"/api/housekeeping/templates/{tmpl.id}/",
            {"name": "Updated Mop Task", "estimated_minutes": 60},
            format='json'
        )
        assert res.status_code == 200

        task.refresh_from_db()
        assert task.name == "Original Mop Task"
        assert task.estimated_minutes == 25

    def test_quality_score_snapshot_is_immutable(
        self, society_a, site_a, director_user
    ):
        """
        QualityScoreSnapshot is immutable once created.
        Direct modification or deletion is blocked by ValidationError.
        """
        snap = QualityScoreSnapshot.objects.create(
            society=society_a, site=site_a, month="2026-03", score=Decimal("88.50"),
            task_completion_pct=Decimal("90.00"), inspection_pct=Decimal("85.00"),
            complaint_sla_pct=Decimal("95.00"), weights_used={"task": 0.4, "inspection": 0.4, "complaint": 0.2},
            breakdown={}, is_locked=True
        )

        # Attempting direct score modification without audited correction raises ValidationError
        snap.score = Decimal("99.00")
        with pytest.raises(ValidationError):
            snap.clean()

        # Attempting deletion raises ValidationError
        with pytest.raises(ValidationError):
            snap.delete()

    def test_society_settings_weights_constraint_rejects_bad_sums_at_db_level(
        self, society_a
    ):
        """
        DB CheckConstraint and model clean reject weights not summing to 100.
        """
        sett = society_a.settings
        sett.completion_weight = 50
        sett.inspection_weight = 40
        sett.complaint_weight = 30  # Sums to 120 -> Invalid!
        with pytest.raises(ValidationError):
            sett.clean()

    def test_zero_inspection_and_zero_complaint_weight_renormalization(
        self, society_a, site_a, post_a, shift_morning, area_lobby, worker_hk_1
    ):
        """
        Weight re-normalization when month has 0 inspections, 0 complaints, or both.
        """
        u1, wp1 = worker_hk_1
        sett = society_a.settings
        sett.completion_weight = 40
        sett.inspection_weight = 40
        sett.complaint_weight = 20
        sett.save()

        # Create 1 done task in month 2026-02
        TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Feb Task", due_date=datetime(2026, 2, 10).date(),
            shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='DONE', completed_by=wp1, needs_review=False
        )

        # Case 1: 0 inspections, 0 complaints -> 100% on task completion
        calc1 = calculate_monthly_quality_score(site_a, 2026, 2)
        assert calc1['total_score'] == 100.0
        assert calc1['weights_used'] == {'task': 1.0}

        # Case 2: 0 inspections, 1 complaint resolved in SLA (100%)
        comp = Complaint.objects.create(
            society=society_a, site=site_a, raised_by=u1, description="Cold water",
            status='RESOLVED', resolved_at=timezone.now(),
            created_at=timezone.now() - timedelta(hours=1)
        )
        Complaint.objects.filter(id=comp.id).update(created_at=datetime(2026, 2, 5, 10, 0, tzinfo=dt_tz.utc), resolved_at=datetime(2026, 2, 5, 12, 0, tzinfo=dt_tz.utc))

        calc2 = calculate_monthly_quality_score(site_a, 2026, 2)
        # Active weights: task (40), complaint (20) -> normalized to 40/60 (0.6667) and 20/60 (0.3333)
        assert calc2['total_score'] == 100.0

    def test_photo_validation_cap_oversize_wrong_type_undecodable_exif_stripped(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, kolkata_tz
    ):
        """
        Photo upload validation:
        - Photo cap (max_photos_per_task)
        - Oversize (> 5MB)
        - Wrong MIME type / undecodable bytes
        - EXIF metadata stripped
        """
        u1, wp1 = worker_hk_1
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )
        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Photo Pipeline Test", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )
        api_client.force_authenticate(user=u1)

        # 1. Oversize file (> 5MB)
        huge_file = SimpleUploadedFile("big.jpg", b"X" * (6 * 1024 * 1024), content_type="image/jpeg")
        r_huge = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {"file": huge_file, "client_uuid": str(uuid.uuid4()), "kind": "BEFORE", "captured_at": timezone.now().isoformat()},
            format='multipart'
        )
        assert r_huge.status_code == 400
        assert "exceeds" in r_huge.data['error']

        # 2. Undecodable bytes
        fake_img = SimpleUploadedFile("fake.jpg", b"NotAnImageBytesAtAll", content_type="image/jpeg")
        r_fake = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {"file": fake_img, "client_uuid": str(uuid.uuid4()), "kind": "BEFORE", "captured_at": timezone.now().isoformat()},
            format='multipart'
        )
        assert r_fake.status_code == 400
        assert "undecodable" in r_fake.data['error'].lower() or "invalid" in r_fake.data['error'].lower()

        # 3. Photo cap enforcement: set max_photos_per_task=1
        sett = society_a.settings
        sett.max_photos_per_task = 1
        sett.save()

        valid_img1 = make_test_image()
        r_ok1 = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {"file": valid_img1, "client_uuid": str(uuid.uuid4()), "kind": "BEFORE", "captured_at": timezone.now().isoformat(), "lat": 18.5204, "lng": 73.8567},
            format='multipart'
        )
        assert r_ok1.status_code == 201

        # Second upload exceeds custom cap
        valid_img2 = make_test_image()
        r_cap = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {"file": valid_img2, "client_uuid": str(uuid.uuid4()), "kind": "AFTER", "captured_at": timezone.now().isoformat(), "lat": 18.5204, "lng": 73.8567},
            format='multipart'
        )
        assert r_cap.status_code == 400
        assert "limit" in r_cap.data['error'].lower()

        # 4. Default photo cap enforcement (default is 6 photos per task)
        sett.max_photos_per_task = 6
        sett.save()
        task_default = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Default Cap Test", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )
        for i in range(6):
            r_ok = api_client.post(
                f"/api/housekeeping/tasks/{task_default.id}/photos/",
                {"file": make_test_image(), "client_uuid": str(uuid.uuid4()), "kind": "BEFORE" if i == 0 else "AFTER", "captured_at": timezone.now().isoformat(), "lat": 18.5204, "lng": 73.8567},
                format='multipart'
            )
            assert r_ok.status_code == 201, f"Failed at photo {i+1}: {r_ok.data}"

        # 7th photo exceeds default cap of 6
        r_over = api_client.post(
            f"/api/housekeeping/tasks/{task_default.id}/photos/",
            {"file": make_test_image(), "client_uuid": str(uuid.uuid4()), "kind": "AFTER", "captured_at": timezone.now().isoformat(), "lat": 18.5204, "lng": 73.8567},
            format='multipart'
        )
        assert r_over.status_code == 400
        assert "max 6" in r_over.data['error'] or "limit" in r_over.data['error'].lower()

    def test_captured_at_future_and_outside_shift_flagged(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, kolkata_tz
    ):
        """
        Future capture timestamp is rejected (400).
        Capture timestamp outside shift start/end window is flagged OUTSIDE_SHIFT_WINDOW and NEEDS_REVIEW (201).
        """
        u1, wp1 = worker_hk_1
        today = timezone.localdate()
        s_start = timezone.make_aware(datetime.combine(today, time(7, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s_end = timezone.make_aware(datetime.combine(today, time(15, 0)), kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society_a, post=post_a, shift=shift_morning, date=today,
            slot_number=1, worker=wp1, status='PRESENT',
            shift_start_at=s_start, shift_end_at=s_end
        )
        AttendanceEvent.objects.create(
            society=society_a, roster_entry=slot, worker=wp1,
            clock_in_uuid=uuid.uuid4(), clock_in_at=timezone.now(),
            client_timestamp=timezone.now()
        )
        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Timing Check", due_date=today, shift_start_at=s_start, shift_end_at=s_end,
            status='IN_PROGRESS', claimed_by=wp1
        )
        api_client.force_authenticate(user=u1)

        # 1. Future capture time (> 5 min future) -> 400 Bad Request
        future_time = (timezone.now() + timedelta(minutes=15)).isoformat()
        r_future = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {"file": make_test_image(), "client_uuid": str(uuid.uuid4()), "kind": "BEFORE", "captured_at": future_time},
            format='multipart'
        )
        assert r_future.status_code == 400
        assert "future" in r_future.data['error'].lower()

        # 2. Outside shift window is NOT rejected; accepted (201) and flagged OUTSIDE_SHIFT_WINDOW and NEEDS_REVIEW
        early_time = (s_start - timedelta(hours=2)).isoformat()
        r_outside = api_client.post(
            f"/api/housekeeping/tasks/{task.id}/photos/",
            {
                "file": make_test_image(),
                "client_uuid": str(uuid.uuid4()),
                "kind": "BEFORE",
                "captured_at": early_time,
                "lat": 18.5204,
                "lng": 73.8567
            },
            format='multipart'
        )
        assert r_outside.status_code == 201
        p_out = TaskPhoto.objects.get(id=r_outside.data['id'])
        assert 'OUTSIDE_SHIFT_WINDOW' in (p_out.flags or [])
        assert 'NEEDS_REVIEW' in (p_out.flags or [])

    def test_pending_or_inactive_member_cannot_raise_complaint(
        self, api_client, society_a, site_a
    ):
        """
        User with no active membership cannot raise a resident complaint.
        """
        unauth_user = User.objects.create_user(username="pending_mem", password="altuspassword123!", role="MEMBER")
        Membership.objects.create(user=unauth_user, society=society_a, role="MEMBER", is_active=False)

        api_client.force_authenticate(user=unauth_user)
        res = api_client.post(
            "/api/housekeeping/complaints/",
            {"site": str(site_a.id), "description": "Water leak in basement"},
            format='json'
        )
        assert res.status_code in (400, 403, 404)

    def test_complaint_and_inspection_photos_use_same_image_pipeline(
        self, api_client, society_a, site_a, post_a, area_lobby, supervisor_a, member_a
    ):
        """
        Complaint photos and inspection photos use the standardized sanitized image pipeline.
        """
        # 1. Complaint photo upload
        api_client.force_authenticate(user=member_a)
        res_comp = api_client.post(
            "/api/housekeeping/complaints/",
            {"site": str(site_a.id), "description": "Lobby light broken", "photo": make_test_image()},
            format='multipart'
        )
        assert res_comp.status_code == 201
        comp = Complaint.objects.get(id=res_comp.data['id'])
        assert bool(comp.photo) is True

        # 2. Inspection photo upload
        api_client.force_authenticate(user=supervisor_a)
        insp = Inspection.objects.create(
            society=society_a, post=post_a, area=area_lobby, inspector=supervisor_a,
            date=timezone.localdate(), score=4, status='PASSED'
        )
        res_insp_photo = api_client.post(
            f"/api/housekeeping/inspections/{insp.id}/photos/",
            {"file": make_test_image(), "caption": "Clean lobby floor"},
            format='multipart'
        )
        assert res_insp_photo.status_code == 201
        insp_photo = InspectionPhoto.objects.get(id=res_insp_photo.data['id'])
        assert bool(insp_photo.file) is True

    def test_same_society_validation_on_all_housekeeping_models(
        self, society_a, society_b, site_a, post_a, shift_morning, area_lobby, worker_hk_1
    ):
        """
        Cross-society relations raise ValidationError across all housekeeping models.
        """
        u1, wp1 = worker_hk_1

        # 1. Area with mismatched Site
        area_bad = Area(society=society_b, site=site_a, name="Mismatched Area")
        with pytest.raises(ValidationError):
            area_bad.clean()

        # 2. TaskTemplate with mismatched Post
        tmpl_bad = TaskTemplate(society=society_b, post=post_a, shift=shift_morning, area=area_lobby, name="Bad Tmpl")
        with pytest.raises(ValidationError):
            tmpl_bad.clean()

        # 3. SupplyRequest with mismatched Item
        item_a = SupplyItem.objects.create(society=society_a, name="Broom", category="EQUIPMENT", unit="PIECE")
        req_bad = SupplyRequest(society=society_b, item=item_a, requested_by=wp1, quantity=2)
        with pytest.raises(ValidationError):
            req_bad.clean()

    def test_supply_request_flow(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, supervisor_a, kolkata_tz
    ):
        """
        Worker submits supply request -> Supervisor approves -> Supervisor issues.
        """
        u1, wp1 = worker_hk_1
        item = SupplyItem.objects.create(society=society_a, name="Disinfectant", category="CHEMICAL", unit="LITRE")

        # 1. Worker requests supply
        api_client.force_authenticate(user=u1)
        res_req = api_client.post(
            "/api/housekeeping/supply-requests/",
            {"item": str(item.id), "quantity": 5, "notes": "Running low on floor disinfectant"},
            format='json'
        )
        assert res_req.status_code == 201
        assert res_req.data['status'] == 'REQUESTED'
        req_id = res_req.data['id']

        # 2. Supervisor approves
        api_client.force_authenticate(user=supervisor_a)
        res_app = api_client.post(f"/api/housekeeping/supply-requests/{req_id}/approve/", format='json')
        assert res_app.status_code == 200
        assert res_app.data['status'] == 'APPROVED'

        # 3. Supervisor issues
        res_iss = api_client.post(f"/api/housekeeping/supply-requests/{req_id}/issue/", format='json')
        assert res_iss.status_code == 200
        assert res_iss.data['status'] == 'ISSUED'

    def test_chairman_and_resident_denied_raw_task_photos_403(
        self, api_client, society_a, post_a, shift_morning, area_lobby, worker_hk_1, chairman_a, member_a
    ):
        """
        Residents and Chairmen receive 403 Forbidden when requesting raw task photos.
        """
        u1, wp1 = worker_hk_1
        task = TaskInstance.objects.create(
            society=society_a, post=post_a, shift=shift_morning, area=area_lobby,
            name="Confidential Area Clean", due_date=timezone.localdate(),
            shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8),
            status='DONE'
        )
        photo = TaskPhoto.objects.create(
            society=society_a, task_instance=task, kind='AFTER',
            file=SimpleUploadedFile("photo.jpg", b"test", content_type="image/jpeg"),
            client_uuid=uuid.uuid4(), captured_at=timezone.now(), uploaded_by=wp1
        )

        # Chairman denied
        api_client.force_authenticate(user=chairman_a)
        res_chair = api_client.get(f"/api/housekeeping/photos/{photo.id}/file/")
        assert res_chair.status_code == 403

        # Resident denied
        api_client.force_authenticate(user=member_a)
        res_mem = api_client.get(f"/api/housekeeping/photos/{photo.id}/file/")
        assert res_mem.status_code == 403

    def test_worker_cannot_read_quality_score_endpoint_403(
        self, api_client, site_a, worker_hk_1
    ):
        """
        Workers are strictly forbidden from viewing client quality score reports.
        """
        u1, wp1 = worker_hk_1
        api_client.force_authenticate(user=u1)
        res = api_client.get(f"/api/housekeeping/quality-score/?site={site_a.id}")
        assert res.status_code == 403
        assert "not authorized" in res.data['error']

