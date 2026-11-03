import io
import uuid
import zoneinfo
from datetime import datetime, time, date, timedelta, timezone as dt_tz
from decimal import Decimal
from PIL import Image
import pytest

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    User, Society, Site, Membership, SocietySettings,
    WorkerProfile, Post, Shift, RosterAssignment, DailyRoster,
    LeaveRecord, AttendanceEvent, Alert, AuditLog
)
from core.staffing_utils import haversine_distance_meters, shifts_overlap


def create_test_image(format='JPEG', size=(100, 100), color='blue'):
    file_io = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(file_io, format=format)
    file_io.seek(0)
    return SimpleUploadedFile(f"selfie_{uuid.uuid4().hex[:6]}.jpg", file_io.read(), content_type='image/jpeg')


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def kolkata_tz():
    return zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.fixture
def society_a(db):
    soc = Society.objects.create(name="Society Alpha", client_type="SOCIETY", address="Pune")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        shift_start_grace_minutes=15,
        early_clock_in_minutes=30,
        early_leave_minutes=15,
        overtime_threshold_minutes=30,
        mock_location_policy='REJECT'
    )
    return soc


@pytest.fixture
def society_b(db):
    soc = Society.objects.create(name="Society Beta", client_type="SOCIETY", address="Mumbai")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        shift_start_grace_minutes=15,
        early_clock_in_minutes=30,
        early_leave_minutes=15,
        overtime_threshold_minutes=30,
        mock_location_policy='REJECT'
    )
    return soc


@pytest.fixture
def site_a(society_a):
    return Site.objects.create(
        society=society_a,
        name="Tower A Gate",
        latitude=Decimal("18.520430"),
        longitude=Decimal("73.856740"),
        geofence_radius_m=100,
        max_gps_accuracy_m=50.0
    )


@pytest.fixture
def site_b(society_b):
    return Site.objects.create(
        society=society_b,
        name="Tower B Gate",
        latitude=Decimal("19.076090"),
        longitude=Decimal("72.877426"),
        geofence_radius_m=100,
        max_gps_accuracy_m=50.0
    )


@pytest.fixture
def director_user(db):
    return User.objects.create_user(username="director_test", password="altuspassword123!", role="DIRECTOR")


@pytest.fixture
def supervisor_a(society_a):
    user = User.objects.create_user(username="sup_alpha", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society_a, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def supervisor_b(society_b):
    user = User.objects.create_user(username="sup_beta", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society_b, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def chairman_a(society_a):
    user = User.objects.create_user(username="chair_alpha", password="altuspassword123!", role="CHAIRMAN")
    Membership.objects.create(user=user, society=society_a, role="CHAIRMAN", is_active=True)
    return user


@pytest.fixture
def member_a(society_a):
    user = User.objects.create_user(username="mem_alpha", password="altuspassword123!", role="MEMBER")
    Membership.objects.create(user=user, society=society_a, role="MEMBER", is_active=True)
    return user


@pytest.fixture
def worker_1(db):
    user = User.objects.create_user(username="worker_one", password="altuspassword123!", role="WORKER")
    profile = WorkerProfile.objects.create(user=user, phone="9999900001", verification_status="VERIFIED")
    return profile


@pytest.fixture
def worker_2(db):
    user = User.objects.create_user(username="worker_two", password="altuspassword123!", role="WORKER")
    profile = WorkerProfile.objects.create(user=user, phone="9999900002", verification_status="VERIFIED")
    return profile


@pytest.fixture
def unverified_worker(db):
    user = User.objects.create_user(username="worker_unverified", password="altuspassword123!", role="WORKER")
    profile = WorkerProfile.objects.create(user=user, phone="9999900003", verification_status="PENDING")
    return profile


@pytest.fixture
def post_a(society_a, site_a):
    return Post.objects.create(
        society=society_a,
        site=site_a,
        name="Main Lobby Housekeeping",
        category="HOUSEKEEPING",
        billing_basis="PER_SHIFT",
        client_rate=Decimal("450.00")
    )


@pytest.fixture
def shift_day_a(society_a, post_a):
    return Shift.objects.create(
        society=society_a,
        post=post_a,
        name="Morning Day Shift",
        start_time=time(8, 0),
        end_time=time(16, 0),
        days_of_week="0,1,2,3,4,5,6",
        required_headcount=1
    )


@pytest.fixture
def shift_night_a(society_a, post_a):
    return Shift.objects.create(
        society=society_a,
        post=post_a,
        name="Overnight Security Shift",
        start_time=time(22, 0),
        end_time=time(6, 0),
        days_of_week="0,1,2,3,4,5,6",
        required_headcount=1
    )


# ─── 1. GEOFENCE & ACCURACY TESTS ────────────────────────────────────────────

def test_geofence_inside_passes(api_client, society_a, site_a, post_a, shift_day_a, worker_1, kolkata_tz):
    api_client.force_authenticate(user=worker_1.user)
    today = timezone.localdate()
    now = timezone.now()

    # Slot for right now
    slot = DailyRoster.objects.create(
        society=society_a,
        post=post_a,
        shift=shift_day_a,
        date=today,
        slot_number=1,
        worker=worker_1,
        status='SCHEDULED',
        shift_start_at=now - timedelta(minutes=10),
        shift_end_at=now + timedelta(hours=7)
    )

    # Coords ~30m from site (lat delta ~0.0002)
    lat = float(site_a.latitude) + 0.0002
    lng = float(site_a.longitude)

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': lat,
        'lng': lng,
        'accuracy': 15.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 201
    assert str(res.data['worker']) == str(worker_1.id)
    slot.refresh_from_db()
    assert slot.status == 'PRESENT'


def test_geofence_outside_fails_with_distance(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    api_client.force_authenticate(user=worker_1.user)
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    # Coords far away (~1.5 km away)
    lat = float(site_a.latitude) + 0.015
    lng = float(site_a.longitude)

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': lat,
        'lng': lng,
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 400
    assert "outside the site geofence" in res.data['error']
    assert res.data['distance_m'] > 100


def test_geofence_boundary_tolerance_passes(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    api_client.force_authenticate(user=worker_1.user)
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    # Earth radius ~ 6371000m. 99.9m distance in lat = 99.9 / 111195.0
    lat_at_100m = float(site_a.latitude) + (99.90 / 111195.0)

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': lat_at_100m,
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 201


def test_bad_gps_accuracy_rejected(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    api_client.force_authenticate(user=worker_1.user)
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    # accuracy = 75m > max_gps_accuracy_m (50.0m)
    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 75.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 400
    assert "GPS accuracy too low" in res.data['error']


def test_mock_location_handling(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    api_client.force_authenticate(user=worker_1.user)
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    # SocietySettings mock_location_policy is REJECT by default
    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'is_mock': True,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 400
    assert "Mock location detected and rejected" in res.data['error']


# ─── 2. OVERNIGHT SHIFT TESTS ────────────────────────────────────────────────

def test_overnight_shift_computation_and_clockin(api_client, society_a, site_a, post_a, shift_night_a, worker_1, kolkata_tz):
    assert shift_night_a.crosses_midnight is True

    # Overnight shift: 22:00 to 06:00
    shift_date = date(2026, 11, 4)
    start_dt = timezone.make_aware(datetime(2026, 11, 4, 22, 0), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime(2026, 11, 5, 6, 0), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a,
        post=post_a,
        shift=shift_night_a,
        date=shift_date,
        slot_number=1,
        worker=worker_1,
        status='SCHEDULED',
        shift_start_at=start_dt,
        shift_end_at=end_dt
    )

    api_client.force_authenticate(user=worker_1.user)

    # Clock in at 11:30 PM (23:30) on Nov 4
    clock_in_time = timezone.make_aware(datetime(2026, 11, 4, 23, 30), kolkata_tz).astimezone(dt_tz.utc)
    cin_uuid = uuid.uuid4()

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(cin_uuid),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': clock_in_time.isoformat()
    }, format='json')

    assert res.status_code == 201
    assert res.data['date'] == '2026-11-04'

    # Clock out at 6:15 AM on Nov 5 (15 min after shift end)
    clock_out_time = timezone.make_aware(datetime(2026, 11, 5, 6, 15), kolkata_tz).astimezone(dt_tz.utc)
    cout_uuid = uuid.uuid4()

    res_out = api_client.post('/api/roster/clock-out/', {
        'clock_out_uuid': str(cout_uuid),
        'roster_entry_id': str(slot.id),
        'client_timestamp': clock_out_time.isoformat()
    }, format='json')

    assert res_out.status_code == 200
    assert res_out.data['date'] == '2026-11-04'
    assert res_out.data['worked_minutes'] == 405  # 6h 45m = 405 min


# ─── 3. OVERLAP PREVENTION & MULTI-HEADCOUNT ─────────────────────────────────

def test_cross_society_and_overnight_overlap_prevention(society_a, society_b, post_a, shift_night_a, worker_1):
    # Assignment 1 on Society A overnight shift (22:00 to 06:00)
    RosterAssignment.objects.create(
        society=society_a,
        worker=worker_1,
        shift=shift_night_a,
        start_date=date(2026, 11, 1),
        status='ACTIVE'
    )

    # Site & Post in Society B
    site_b = Site.objects.create(society=society_b, name="Site B", latitude=19.0, longitude=72.0)
    post_b = Post.objects.create(society=society_b, site=site_b, name="Post B")
    # Shift in Society B: Early morning shift 05:00 to 13:00 (overlaps 05:00-06:00 with night shift!)
    shift_overlap = Shift.objects.create(
        society=society_b,
        post=post_b,
        name="Early Morning",
        start_time=time(5, 0),
        end_time=time(13, 0),
        days_of_week="0,1,2,3,4,5,6"
    )

    # Attempt to assign worker_1 to overlapping shift in Society B
    with pytest.raises(ValidationError) as exc:
        asgn2 = RosterAssignment(
            society=society_b,
            worker=worker_1,
            shift=shift_overlap,
            start_date=date(2026, 11, 1),
            status='ACTIVE'
        )
        asgn2.full_clean()

    assert "overlapping hours during this period" in str(exc.value)


def test_multi_headcount_slots(society_a, post_a, worker_1, worker_2):
    shift_2 = Shift.objects.create(
        society=society_a,
        post=post_a,
        name="Team Shift",
        start_time=time(9, 0),
        end_time=time(17, 0),
        required_headcount=2,
        days_of_week="0,1,2,3,4,5,6"
    )

    RosterAssignment.objects.create(society=society_a, worker=worker_1, shift=shift_2, start_date=date(2026, 11, 1))
    RosterAssignment.objects.create(society=society_a, worker=worker_2, shift=shift_2, start_date=date(2026, 11, 1))

    # Generate roster
    call_command('generate_roster', days=1, date='2026-11-04')

    slots = DailyRoster.objects.filter(shift=shift_2, date=date(2026, 11, 4)).order_by('slot_number')
    assert slots.count() == 2
    assert slots[0].worker == worker_1
    assert slots[0].status == 'SCHEDULED'
    assert slots[1].worker == worker_2
    assert slots[1].status == 'SCHEDULED'


# ─── 4. IDEMPOTENCY & CROSS-WORKER LEAK PREVENTION ───────────────────────────

def test_idempotent_clock_in_and_cross_worker_uuid_isolation(api_client, society_a, site_a, post_a, shift_day_a, worker_1, worker_2):
    now = timezone.now()
    slot1 = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )
    cin_uuid = uuid.uuid4()

    api_client.force_authenticate(user=worker_1.user)

    # 1st Clock in
    res1 = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(cin_uuid),
        'roster_entry_id': str(slot1.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')
    assert res1.status_code == 201

    # 2nd Clock in with same uuid by worker 1 (Idempotent retry)
    res2 = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(cin_uuid),
        'roster_entry_id': str(slot1.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')
    assert res2.status_code == 200
    assert AttendanceEvent.objects.count() == 1

    # Worker 2 attempts to use worker 1's clock_in_uuid
    api_client.force_authenticate(user=worker_2.user)
    slot2 = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=2, worker=worker_2, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    res3 = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(cin_uuid),
        'roster_entry_id': str(slot2.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    # Worker 2 creates their OWN event with this UUID; never leaks worker 1's data
    assert res3.status_code == 201
    assert str(res3.data['worker']) == str(worker_2.id)
    assert AttendanceEvent.objects.count() == 2


# ─── 5. FLAGS & ALERTS ───────────────────────────────────────────────────────

def test_lateness_alert_and_overtime_flags(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    now = timezone.now()
    # Shift started 45 minutes ago (grace is 15 mins)
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now - timedelta(minutes=45),
        shift_end_at=now + timedelta(hours=7)
    )

    api_client.force_authenticate(user=worker_1.user)

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 201
    assert 'LATE' in res.data['flags']
    assert Alert.objects.filter(roster_entry=slot, alert_type='LATE').count() == 1

    # Clock out 45 min after shift end (overtime threshold is 30 mins)
    res_out = api_client.post('/api/roster/clock-out/', {
        'clock_out_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'client_timestamp': (slot.shift_end_at + timedelta(minutes=45)).isoformat()
    }, format='json')

    assert res_out.status_code == 200
    assert 'OVERTIME' in res_out.data['flags']


# ─── 6. SELFIE ENFORCEMENT & SECURITY ────────────────────────────────────────

def test_selfie_required_and_permission_isolation(api_client, society_a, society_b, site_a, post_a, shift_day_a, worker_1, supervisor_b, chairman_a):
    society_a.settings.selfie_required = True
    society_a.settings.save()

    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    api_client.force_authenticate(user=worker_1.user)

    # Missing selfie fails
    res_no_selfie = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='multipart')
    assert res_no_selfie.status_code == 400
    assert "Selfie photo is required" in res_no_selfie.data['error']

    # With valid image passes
    img_file = create_test_image()
    res_with_selfie = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat(),
        'selfie': img_file
    }, format='multipart')
    assert res_with_selfie.status_code == 201
    event_id = res_with_selfie.data['id']

    # Worker can download their own selfie
    selfie_url = f"/api/roster/attendance/{event_id}/selfie/"
    res_worker_get = api_client.get(selfie_url)
    assert res_worker_get.status_code == 200

    # Cross-society supervisor gets 404
    api_client.force_authenticate(user=supervisor_b)
    res_sup_b = api_client.get(selfie_url)
    assert res_sup_b.status_code == 404

    # Chairman of Society A gets 404 (worker private media access blocked)
    api_client.force_authenticate(user=chairman_a)
    res_chair = api_client.get(selfie_url)
    assert res_chair.status_code == 404


# ─── 7. LEAVE APPROVAL & UNFILLED SLOTS ───────────────────────────────────────

def test_late_leave_approval_marks_slots_unfilled_with_alert(api_client, society_a, post_a, shift_day_a, worker_1, supervisor_a):
    RosterAssignment.objects.create(society=society_a, worker=worker_1, shift=shift_day_a, start_date=date(2026, 11, 1))

    # Generate roster for tomorrow
    tomorrow = timezone.localdate() + timedelta(days=1)
    call_command('generate_roster', days=1, date=tomorrow.isoformat())

    slot = DailyRoster.objects.get(shift=shift_day_a, date=tomorrow)
    assert slot.worker == worker_1
    assert slot.status == 'SCHEDULED'

    # Worker submits leave
    leave = LeaveRecord.objects.create(
        society=society_a,
        worker=worker_1,
        start_date=tomorrow,
        end_date=tomorrow,
        leave_type='SICK',
        status='PENDING'
    )

    # Supervisor approves leave
    api_client.force_authenticate(user=supervisor_a)
    res = api_client.post(f"/api/roster/leaves/{leave.id}/approve/")
    assert res.status_code == 200

    slot.refresh_from_db()
    assert slot.worker is None
    assert slot.status == 'UNFILLED'
    assert Alert.objects.filter(roster_entry=slot, alert_type='UNFILLED').exists()


# ─── 8. SAME-SOCIETY VALIDATION ──────────────────────────────────────────────

def test_same_society_consistency_validation(society_a, society_b, site_a, post_a):
    # Post with site from different society
    with pytest.raises(ValidationError) as exc:
        p = Post(society=society_b, site=site_a, name="Cross Society Post")
        p.full_clean()
    assert "Site must belong to the same society" in str(exc.value)

    # Shift with post from different society
    with pytest.raises(ValidationError) as exc:
        s = Shift(society=society_b, post=post_a, name="Cross Shift", start_time=time(8, 0), end_time=time(16, 0))
        s.full_clean()
    assert "Post must belong to the same society" in str(exc.value)


# ─── 9. SUPERVISOR ATTENDANCE CORRECTION & AUDIT ─────────────────────────────

def test_supervisor_attendance_correction_audit(api_client, society_a, site_a, post_a, shift_day_a, worker_1, supervisor_a):
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='PRESENT',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )
    event = AttendanceEvent.objects.create(
        society=society_a, roster_entry=slot, worker=worker_1,
        clock_in_at=now, client_timestamp=now
    )

    api_client.force_authenticate(user=supervisor_a)

    # Missing reason fails
    res_fail = api_client.post(f"/api/roster/attendance/{event.id}/correct/", {
        'clock_out_at': (now + timedelta(hours=8)).isoformat()
    }, format='json')
    assert res_fail.status_code == 400

    # With reason succeeds and creates AuditLog
    corr_time = now + timedelta(hours=8)
    res_ok = api_client.post(f"/api/roster/attendance/{event.id}/correct/", {
        'clock_out_at': corr_time.isoformat(),
        'reason': 'Worker forgot to clock out at turnstile.'
    }, format='json')

    assert res_ok.status_code == 200
    assert res_ok.data['worked_minutes'] == 480
    assert AuditLog.objects.filter(target_id=event.id, action='ATTENDANCE_CORRECTION').exists()


# ─── 10. MARK ABSENT COMMAND & UNFILLED LOGIC ────────────────────────────────

def test_mark_absent_command(society_a, post_a, shift_day_a, worker_1):
    past_start = timezone.now() - timedelta(hours=2)
    # Slot 1: Has worker, no clock-in
    slot_assigned = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=past_start.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=past_start, shift_end_at=past_start + timedelta(hours=8)
    )

    # Slot 2: Unfilled
    slot_empty = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=past_start.date(),
        slot_number=2, worker=None, status='UNFILLED',
        shift_start_at=past_start, shift_end_at=past_start + timedelta(hours=8)
    )

    call_command('mark_absent_shifts', grace_minutes=30)

    slot_assigned.refresh_from_db()
    assert slot_assigned.status == 'ABSENT'
    assert Alert.objects.filter(roster_entry=slot_assigned, alert_type='ABSENT').exists()

    slot_empty.refresh_from_db()
    assert slot_empty.status == 'UNFILLED'
    assert Alert.objects.filter(roster_entry=slot_empty, alert_type='UNFILLED').exists()


# ─── 11. CROSS-SOCIETY ISOLATION (404) ───────────────────────────────────────

def test_cross_society_crud_and_clockin_isolation(api_client, society_a, society_b, post_a, shift_day_a, supervisor_b, worker_1):
    # Supervisor of Society B tries to view/edit Society A Post
    api_client.force_authenticate(user=supervisor_b)

    res_get = api_client.get(f"/api/roster/posts/{post_a.id}/")
    assert res_get.status_code == 404

    res_patch = api_client.patch(f"/api/roster/posts/{post_a.id}/", {'name': 'Hacked'})
    assert res_patch.status_code == 404

    res_del = api_client.delete(f"/api/roster/posts/{post_a.id}/")
    assert res_del.status_code == 404


# ─── 12. EXTRA CORNER-CASE & CONCURRENCY TESTS ───────────────────────────────

def test_unverified_worker_cannot_clock_in(api_client, society_a, site_a, post_a, shift_day_a, unverified_worker):
    api_client.force_authenticate(user=unverified_worker.user)
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=unverified_worker, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 403
    assert "not yet verified" in res.data['error']


def test_worker_cannot_clock_in_to_another_workers_slot(api_client, society_a, site_a, post_a, shift_day_a, worker_1, worker_2):
    now = timezone.now()
    slot_for_worker_2 = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_2, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    # Worker 1 attempts to clock in to Worker 2's slot
    api_client.force_authenticate(user=worker_1.user)
    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot_for_worker_2.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 403
    assert "You are not assigned to this roster slot" in res.data['error']


def test_offline_clock_out_preserves_client_timestamp_and_flags_mismatch(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='PRESENT',
        shift_start_at=now - timedelta(hours=4), shift_end_at=now + timedelta(hours=4)
    )
    cin_time = now - timedelta(hours=4)
    event = AttendanceEvent.objects.create(
        society=society_a, roster_entry=slot, worker=worker_1,
        clock_in_at=cin_time, client_timestamp=cin_time
    )

    api_client.force_authenticate(user=worker_1.user)

    # Worker was offline and syncs 3 hours after actual clock-out
    offline_cout_time = cin_time + timedelta(hours=3)
    cout_uuid = uuid.uuid4()

    res = api_client.post('/api/roster/clock-out/', {
        'clock_out_uuid': str(cout_uuid),
        'roster_entry_id': str(slot.id),
        'client_timestamp': offline_cout_time.isoformat()
    }, format='json')

    assert res.status_code == 200
    event.refresh_from_db()
    # Recorded clock_out_at is the offline client timestamp, not server 'now'
    assert event.clock_out_at == offline_cout_time
    assert event.time_mismatch_flag is True
    assert event.worked_minutes == 180  # Exactly 3h


def test_concurrent_clock_in_second_request_returns_409(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    now = timezone.now()
    slot = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_day_a, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    api_client.force_authenticate(user=worker_1.user)

    # 1st clock-in
    res1 = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')
    assert res1.status_code == 201

    # 2nd clock-in with a different uuid (concurrent or double clock-in attempt on same slot)
    res2 = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot.id),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res2.status_code == 409
    assert "already has an attendance record" in res2.data['error']


def test_back_to_back_shifts_deterministic_slot_choice(api_client, society_a, site_a, post_a, shift_day_a, worker_1):
    now = timezone.now()

    # Shift 1: 06:00 to 14:00 (ended just now, slot already completed)
    shift_1 = Shift.objects.create(
        society=society_a, post=post_a, name="Shift 1 Morning",
        start_time=time(6, 0), end_time=time(14, 0), days_of_week="0,1,2,3,4,5,6"
    )
    slot1 = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_1, date=now.date(),
        slot_number=1, worker=worker_1, status='COMPLETED',
        shift_start_at=now - timedelta(hours=8), shift_end_at=now
    )
    AttendanceEvent.objects.create(
        society=society_a, roster_entry=slot1, worker=worker_1,
        clock_in_at=now - timedelta(hours=8), clock_out_at=now,
        client_timestamp=now
    )

    # Shift 2: 14:00 to 22:00 (starting right now, unclocked)
    shift_2 = Shift.objects.create(
        society=society_a, post=post_a, name="Shift 2 Afternoon",
        start_time=time(14, 0), end_time=time(22, 0), days_of_week="0,1,2,3,4,5,6"
    )
    slot2 = DailyRoster.objects.create(
        society=society_a, post=post_a, shift=shift_2, date=now.date(),
        slot_number=1, worker=worker_1, status='SCHEDULED',
        shift_start_at=now, shift_end_at=now + timedelta(hours=8)
    )

    api_client.force_authenticate(user=worker_1.user)

    # Clock in without specifying roster_entry_id -> should deterministically select slot2
    res = api_client.post('/api/roster/clock-in/', {
        'clock_in_uuid': str(uuid.uuid4()),
        'lat': float(site_a.latitude),
        'lng': float(site_a.longitude),
        'accuracy': 10.0,
        'client_timestamp': now.isoformat()
    }, format='json')

    assert res.status_code == 201
    assert res.data['roster_entry'] == slot2.id


