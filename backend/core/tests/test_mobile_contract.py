"""
backend/core/tests/test_mobile_contract.py
Real Django integration contract test suite verifying the exact requests and payloads
produced by Altsan Worker mobile app request builders against the real views and database.
"""
import io
import uuid
from datetime import datetime, timedelta
from PIL import Image
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    User, WorkerProfile, Society, Site, Post, Shift, Area,
    DailyRoster, AttendanceEvent, TaskTemplate, TaskInstance,
    TaskPhoto, ReplacementRequest, ReplacementOffer, Membership
)
from core.views_otp import (
    WorkerOTPVerifyView, IssueFallbackLoginCodeView, RevokeWorkerSessionsView
)
from core.views_staffing import (
    RosterClockInView, RosterClockOutView, MyScheduleView,
    MyOffersView, AcceptOfferView, DeclineOfferView
)
from core.views_housekeeping import TaskInstanceViewSet


def create_test_image_file(name="selfie.jpg"):
    img = Image.new('RGB', (100, 100), color='blue')
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='JPEG')
    byte_arr.name = name
    byte_arr.seek(0)
    return byte_arr


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def seeded_facility(db):
    """Seed test society, site, post, shift, and 2 workers."""
    society = Society.objects.create(name="Prestige Towers")
    site = Site.objects.create(
        society=society,
        name="Main Tower Gate",
        latitude=18.520400,
        longitude=73.856700,
        geofence_radius_m=100,
        max_gps_accuracy_m=50.0
    )
    post = Post.objects.create(
        society=society,
        site=site,
        name="Housekeeping Area A",
        category="HOUSEKEEPING"
    )

    now = timezone.now()
    today = now.date()
    shift_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    shift_end = now.replace(hour=17, minute=0, second=0, microsecond=0)

    shift = Shift.objects.create(
        society=society,
        post=post,
        name="Day Shift",
        start_time=shift_start.time(),
        end_time=shift_end.time()
    )

    # Worker 1
    u1 = User.objects.create_user(username="worker_contract_1", password="TestPassword123!", role="WORKER")
    w1 = WorkerProfile.objects.create(
        user=u1,
        phone="+919876543201",
        verification_status="VERIFIED"
    )

    # Worker 2
    u2 = User.objects.create_user(username="worker_contract_2", password="TestPassword123!", role="WORKER")
    w2 = WorkerProfile.objects.create(
        user=u2,
        phone="+919876543202",
        verification_status="VERIFIED"
    )

    # Supervisor
    u_sup = User.objects.create_user(username="sup_contract_1", password="TestPassword123!", role="SUPERVISOR")
    Membership.objects.create(user=u_sup, society=society, role="SUPERVISOR", is_active=True)

    # Roster Slots
    slot1 = DailyRoster.objects.create(
        society=society,
        post=post,
        shift=shift,
        worker=w1,
        date=today,
        slot_number=1,
        status="SCHEDULED",
        shift_start_at=now - timedelta(minutes=15),
        shift_end_at=now + timedelta(hours=8)
    )

    area = Area.objects.create(
        society=society,
        site=site,
        name="Lobby Area",
        floor_or_block="Ground"
    )

    # Housekeeping Task
    template = TaskTemplate.objects.create(
        society=society,
        post=post,
        area=area,
        shift=shift,
        name="Lobby Floor Sanitization",
        frequency="DAILY",
        photo_required="BEFORE_AFTER"
    )

    task1 = TaskInstance.objects.create(
        society=society,
        template=template,
        post=post,
        area=area,
        shift=shift,
        name="Lobby Floor Sanitization",
        photo_required="BEFORE_AFTER",
        due_date=today,
        shift_start_at=slot1.shift_start_at,
        shift_end_at=slot1.shift_end_at,
        status="PENDING"
    )

    return {
        'society': society,
        'site': site,
        'post': post,
        'shift': shift,
        'worker1': (u1, w1),
        'worker2': (u2, w2),
        'supervisor': u_sup,
        'slot1': slot1,
        'task1': task1,
    }


# ── 1. OTP Login with Supervisor-Issued Code & Verify Contract ──────────
@pytest.mark.django_db
def test_supervisor_issued_code_and_otp_verify_contract(api_client, seeded_facility):
    sup = seeded_facility['supervisor']
    u1, w1 = seeded_facility['worker1']

    # 1. Supervisor issues code
    api_client.force_authenticate(user=sup)
    res_issue = api_client.post(f"/api/workers/{w1.id}/issue-login-code/", {
        "reason": "Worker phone offline SMS gateway delay."
    }, format='json')

    assert res_issue.status_code == status.HTTP_200_OK
    issued_code = res_issue.data['login_code']
    assert len(issued_code) == 6

    # 2. Worker verifies issued code via /api/auth/otp/verify/
    api_client.logout()
    res_verify = api_client.post("/api/auth/otp/verify/", {
        "phone": "+919876543201",
        "code": issued_code,
        "device_id": "test_device_pilot_1"
    }, format='json')

    assert res_verify.status_code == status.HTTP_200_OK
    assert 'access' in res_verify.data
    assert 'refresh' in res_verify.data
    assert res_verify.data['worker_id'] == str(w1.id)
    assert res_verify.data['verification_status'] == 'VERIFIED'


# ── 2. Token Refresh & Session Revocation Contract ──────────────────────
@pytest.mark.django_db
def test_token_refresh_and_revoked_session_contract(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(u1)
    access_token = str(refresh.access_token)

    # Refresh token endpoint
    res_refresh = api_client.post("/api/auth/refresh/", {
        "refresh": str(refresh)
    }, format='json')
    assert res_refresh.status_code == status.HTTP_200_OK
    assert 'access' in res_refresh.data

    # Director revokes session
    dir_user = User.objects.create_user(username="director_revoker", password="TestPassword123!", role="DIRECTOR")
    api_client.force_authenticate(user=dir_user)
    res_revoke = api_client.post(f"/api/workers/{w1.id}/revoke-sessions/", {
        "reason": "Device reported lost."
    }, format='json')
    assert res_revoke.status_code == status.HTTP_200_OK

    # Calling an endpoint with old access token must yield 401 session_revoked
    api_client.logout()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    res_protected = api_client.get("/api/roster/my-schedule/")
    assert res_protected.status_code == status.HTTP_401_UNAUTHORIZED
    assert 'session_revoked' in str(res_protected.data)


# ── 3. Schedule Fetch Contract ──────────────────────────────────────────
@pytest.mark.django_db
def test_my_schedule_contract(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    slot1 = seeded_facility['slot1']

    api_client.force_authenticate(user=u1)
    res = api_client.get("/api/roster/my-schedule/")
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.data, list)
    assert len(res.data) >= 1

    entry = res.data[0]
    assert entry['roster_entry_id'] == str(slot1.id)
    assert entry['site_name'] == "Main Tower Gate"
    assert entry['post_name'] == "Housekeeping Area A"
    assert entry['shift_name'] == "Day Shift"
    assert entry['status'] == "SCHEDULED"


# ── 4. Clock-In Inside Geofence & Idempotent Replay Contract ────────────
@pytest.mark.django_db
def test_clock_in_inside_geofence_and_idempotent_replay(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    slot1 = seeded_facility['slot1']
    site = seeded_facility['site']

    api_client.force_authenticate(user=u1)
    clock_in_uuid = str(uuid.uuid4())
    client_ts = timezone.now().isoformat()
    selfie_file = create_test_image_file("selfie.jpg")

    payload = {
        'clock_in_uuid': clock_in_uuid,
        'roster_entry_id': str(slot1.id),
        'lat': site.latitude,
        'lng': site.longitude,
        'accuracy': 12.5,
        'client_timestamp': client_ts,
        'selfie': selfie_file,
    }

    # 1. First Clock-in Attempt (Fresh: returns 201 Created)
    res1 = api_client.post("/api/roster/clock-in/", payload, format='multipart')
    assert res1.status_code == status.HTTP_201_CREATED
    assert res1.data['clock_in_uuid'] == clock_in_uuid
    assert str(res1.data['worker']) == str(w1.id)
    assert res1.data['time_mismatch_flag'] is False
    first_event_id = res1.data['id']

    # Refresh slot
    slot1.refresh_from_db()
    assert slot1.status == "PRESENT"

    # 2. Repeated Replay with same clock_in_uuid (returns 200 OK with original record)
    selfie_file.seek(0)
    res2 = api_client.post("/api/roster/clock-in/", payload, format='multipart')
    assert res2.status_code == status.HTTP_200_OK
    assert res2.data['id'] == first_event_id
    assert res2.data['clock_in_uuid'] == clock_in_uuid

    # Assert only 1 AttendanceEvent in database (Zero duplicates)
    assert AttendanceEvent.objects.filter(worker=w1, clock_in_uuid=clock_in_uuid).count() == 1


# ── 5. Clock-In Outside Geofence Contract ───────────────────────────────
@pytest.mark.django_db
def test_clock_in_outside_geofence_contract(api_client, seeded_facility):
    u2, w2 = seeded_facility['worker2']
    shift = seeded_facility['shift']
    post = seeded_facility['post']
    society = seeded_facility['society']

    now = timezone.now()
    slot2 = DailyRoster.objects.create(
        society=society,
        post=post,
        shift=shift,
        worker=w2,
        date=now.date(),
        slot_number=2,
        status="SCHEDULED",
        shift_start_at=now - timedelta(minutes=10),
        shift_end_at=now + timedelta(hours=8)
    )

    api_client.force_authenticate(user=u2)
    # Coordinates 50 km away
    far_lat = 19.0760
    far_lng = 72.8777
    selfie_file = create_test_image_file("selfie_far.jpg")

    payload = {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot2.id),
        'lat': far_lat,
        'lng': far_lng,
        'accuracy': 15.0,
        'client_timestamp': now.isoformat(),
        'selfie': selfie_file,
    }

    res = api_client.post("/api/roster/clock-in/", payload, format='multipart')
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "Worker is outside the site geofence." in res.data['error']
    assert 'distance_m' in res.data
    assert 'geofence_radius_m' in res.data
    assert res.data['geofence_radius_m'] == 100


# ── 6. Clock-In on Covered Slot (409 Conflict Contract) ─────────────────
@pytest.mark.django_db
def test_clock_in_on_covered_slot_returns_409_conflict(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    u2, w2 = seeded_facility['worker2']
    slot1 = seeded_facility['slot1']
    site = seeded_facility['site']

    # Slot is covered by Worker 2
    slot1.status = 'COVERED'
    slot1.covered_by = w2
    slot1.save(update_fields=['status', 'covered_by'])

    api_client.force_authenticate(user=u1)
    selfie_file = create_test_image_file()

    payload = {
        'clock_in_uuid': str(uuid.uuid4()),
        'roster_entry_id': str(slot1.id),
        'lat': site.latitude,
        'lng': site.longitude,
        'accuracy': 10.0,
        'selfie': selfie_file,
    }

    res = api_client.post("/api/roster/clock-in/", payload, format='multipart')
    assert res.status_code == status.HTTP_409_CONFLICT
    assert "reassigned to a replacement worker" in res.data['error']


# ── 7. Clock-Out Contract (Fresh & Idempotent Replay) ───────────────────
@pytest.mark.django_db
def test_clock_out_and_idempotent_replay(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    slot1 = seeded_facility['slot1']

    # Prepare active clocked-in session
    event = AttendanceEvent.objects.create(
        society=slot1.society,
        roster_entry=slot1,
        worker=w1,
        clock_in_uuid=uuid.uuid4(),
        clock_in_at=timezone.now() - timedelta(hours=4),
        client_timestamp=timezone.now() - timedelta(hours=4),
        latitude=18.5204,
        longitude=73.8567,
        gps_accuracy_m=10.0
    )
    slot1.status = 'PRESENT'
    slot1.save()

    api_client.force_authenticate(user=u1)
    clock_out_uuid = str(uuid.uuid4())
    client_ts = timezone.now().isoformat()

    payload = {
        'clock_out_uuid': clock_out_uuid,
        'roster_entry_id': str(slot1.id),
        'client_timestamp': client_ts,
    }

    # 1. Fresh clock-out
    res1 = api_client.post("/api/roster/clock-out/", payload, format='json')
    assert res1.status_code == status.HTTP_200_OK
    assert res1.data['clock_out_uuid'] == clock_out_uuid
    assert res1.data['worked_minutes'] >= 240

    slot1.refresh_from_db()
    assert slot1.status == 'COMPLETED'

    # 2. Idempotent replay with same clock_out_uuid
    res2 = api_client.post("/api/roster/clock-out/", payload, format='json')
    assert res2.status_code == status.HTTP_200_OK
    assert res2.data['clock_out_uuid'] == clock_out_uuid


# ── 8. Housekeeping Two-Worker Concurrency Test (/claim/ 409 Loser) ─────
@pytest.mark.django_db
def test_two_workers_claiming_same_task_returns_409(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    u2, w2 = seeded_facility['worker2']
    task1 = seeded_facility['task1']
    slot1 = seeded_facility['slot1']

    # Worker 1 clocked in
    AttendanceEvent.objects.create(
        society=slot1.society,
        roster_entry=slot1,
        worker=w1,
        clock_in_uuid=uuid.uuid4(),
        clock_in_at=timezone.now() - timedelta(hours=1),
        client_timestamp=timezone.now() - timedelta(hours=1),
        latitude=18.5204,
        longitude=73.8567,
        gps_accuracy_m=10.0
    )

    # Worker 2 also assigned and clocked in to a slot on the same shift
    slot2 = DailyRoster.objects.create(
        society=seeded_facility['society'],
        post=seeded_facility['post'],
        shift=seeded_facility['shift'],
        worker=w2,
        date=timezone.now().date(),
        slot_number=3,
        status="PRESENT",
        shift_start_at=slot1.shift_start_at,
        shift_end_at=slot1.shift_end_at
    )
    AttendanceEvent.objects.create(
        society=slot2.society,
        roster_entry=slot2,
        worker=w2,
        clock_in_uuid=uuid.uuid4(),
        clock_in_at=timezone.now() - timedelta(hours=1),
        client_timestamp=timezone.now() - timedelta(hours=1),
        latitude=18.5204,
        longitude=73.8567,
        gps_accuracy_m=10.0
    )

    # Worker 1 claims task
    api_client.force_authenticate(user=u1)
    res1 = api_client.post(f"/api/housekeeping/tasks/{task1.id}/claim/", {
        "action_timestamp": timezone.now().isoformat()
    }, format='json')
    assert res1.status_code == status.HTTP_200_OK
    assert res1.data['status'] == 'IN_PROGRESS'

    # Worker 2 attempts to claim the same task
    api_client.force_authenticate(user=u2)
    res2 = api_client.post(f"/api/housekeeping/tasks/{task1.id}/claim/", {
        "action_timestamp": timezone.now().isoformat()
    }, format='json')
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already been claimed" in res2.data['error']


# ── 9. Task Photo Upload & Complete with Expected UUIDs Contract ────────
@pytest.mark.django_db
def test_task_photo_upload_and_complete_with_expected_uuids(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    task1 = seeded_facility['task1']
    slot1 = seeded_facility['slot1']
    site = seeded_facility['site']

    # Worker 1 is clocked in
    AttendanceEvent.objects.create(
        society=slot1.society,
        roster_entry=slot1,
        worker=w1,
        clock_in_uuid=uuid.uuid4(),
        clock_in_at=timezone.now() - timedelta(hours=1),
        client_timestamp=timezone.now() - timedelta(hours=1),
        latitude=18.5204,
        longitude=73.8567,
        gps_accuracy_m=10.0
    )

    api_client.force_authenticate(user=u1)
    photo_client_uuid = str(uuid.uuid4())
    img_file = create_test_image_file("task_photo.jpg")

    # 1. Upload photo with gps_accuracy_m (strictly required)
    photo_payload = {
        'client_uuid': photo_client_uuid,
        'kind': 'BEFORE',
        'lat': site.latitude,
        'lng': site.longitude,
        'gps_accuracy_m': 10.0,
        'captured_at': timezone.now().isoformat(),
        'file': img_file,
    }
    res_photo = api_client.post(f"/api/housekeeping/tasks/{task1.id}/photos/", photo_payload, format='multipart')
    assert res_photo.status_code == status.HTTP_201_CREATED
    assert res_photo.data['client_uuid'] == photo_client_uuid

    # 2. Idempotent photo upload replay
    img_file.seek(0)
    res_photo_replay = api_client.post(f"/api/housekeeping/tasks/{task1.id}/photos/", photo_payload, format='multipart')
    assert res_photo_replay.status_code == status.HTTP_200_OK

    # 3. Complete task with expected_photo_uuids (Awaiting Evidence)
    expected_after_uuid = str(uuid.uuid4())
    res_complete = api_client.post(f"/api/housekeeping/tasks/{task1.id}/complete/", {
        'action_timestamp': timezone.now().isoformat(),
        'expected_photo_uuids': [expected_after_uuid]
    }, format='json')

    assert res_complete.status_code == status.HTTP_200_OK
    assert res_complete.data['status'] == 'AWAITING_EVIDENCE'
    assert expected_after_uuid in res_complete.data['expected_photo_uuids']


# ── 10. Replacement Offers Accept (409 Loser) & Decline Contract ────────
@pytest.mark.django_db
def test_replacement_offers_accept_concurrency_and_decline(api_client, seeded_facility):
    u1, w1 = seeded_facility['worker1']
    u2, w2 = seeded_facility['worker2']
    society = seeded_facility['society']
    slot1 = seeded_facility['slot1']

    # Create replacement request & offers to both workers
    now = timezone.now()
    rep_req = ReplacementRequest.objects.create(
        society=society,
        roster_entry=slot1,
        reason="EMERGENCY_LEAVE",
        status="OFFERING"
    )

    offer1 = ReplacementOffer.objects.create(
        society=society,
        request=rep_req,
        worker=w1,
        status="OFFERED",
        expires_at=now + timedelta(minutes=5)
    )

    offer2 = ReplacementOffer.objects.create(
        society=society,
        request=rep_req,
        worker=w2,
        status="OFFERED",
        expires_at=now + timedelta(minutes=5)
    )

    # 1. Worker 1 views my-offers
    api_client.force_authenticate(user=u1)
    res_offers = api_client.get("/api/roster/my-offers/")
    assert res_offers.status_code == status.HTTP_200_OK
    assert any(o['id'] == str(offer1.id) for o in res_offers.data)

    # 2. Worker 1 accepts offer -> 200 OK
    res_accept1 = api_client.post(f"/api/roster/offers/{offer1.id}/accept/")
    assert res_accept1.status_code == status.HTTP_200_OK
    assert res_accept1.data['status'] == 'ACCEPTED'

    # 3. Worker 2 tries to accept offer2 for same slot -> 409 Conflict
    api_client.force_authenticate(user=u2)
    res_accept2 = api_client.post(f"/api/roster/offers/{offer2.id}/accept/")
    assert res_accept2.status_code == status.HTTP_409_CONFLICT
    assert "no longer available" in res_accept2.data['error']

    # 4. Decline another request offer
    slot_extra = DailyRoster.objects.create(
        society=society,
        post=seeded_facility['post'],
        shift=seeded_facility['shift'],
        date=now.date(),
        slot_number=99,
        status="UNFILLED",
        shift_start_at=slot1.shift_start_at,
        shift_end_at=slot1.shift_end_at
    )
    rep_req_decline = ReplacementRequest.objects.create(
        society=society,
        roster_entry=slot_extra,
        reason="UNFILLED_SHIFT",
        status="OFFERING"
    )
    offer_decline = ReplacementOffer.objects.create(
        society=society,
        request=rep_req_decline,
        worker=w2,
        status="OFFERED",
        expires_at=now + timedelta(minutes=10)
    )
    res_decline = api_client.post(f"/api/roster/offers/{offer_decline.id}/decline/", {
        "reason": "Personal conflict"
    }, format='json')
    assert res_decline.status_code == status.HTTP_200_OK
    assert res_decline.data['status'] == 'DECLINED'
