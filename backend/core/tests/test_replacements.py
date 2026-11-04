import math
import uuid
import zoneinfo
from datetime import datetime, time, date, timedelta, timezone as dt_tz
from decimal import Decimal
import pytest

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    User, Society, Site, Membership, SocietySettings,
    WorkerProfile, Post, Shift, RosterAssignment, DailyRoster,
    LeaveRecord, AttendanceEvent, Alert, AuditLog,
    ReplacementRequest, ReplacementOffer, Notification
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def kolkata_tz():
    return zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.fixture
def society_a(db):
    soc = Society.objects.create(name="Alpha Society", client_type="SOCIETY", address="Pune")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        shift_start_grace_minutes=15,
        early_clock_in_minutes=30,
        early_leave_minutes=15,
        overtime_threshold_minutes=30,
        mock_location_policy='REJECT',
        replacement_offer_expiry_minutes=15,
        replacement_escalation_minutes=60,
        min_rest_gap_hours=8
    )
    return soc


@pytest.fixture
def society_b(db):
    soc = Society.objects.create(name="Beta Society", client_type="SOCIETY", address="Mumbai")
    SocietySettings.objects.create(
        society=soc,
        selfie_required=False,
        shift_start_grace_minutes=15,
        early_clock_in_minutes=30,
        early_leave_minutes=15,
        overtime_threshold_minutes=30,
        mock_location_policy='REJECT',
        replacement_offer_expiry_minutes=15,
        replacement_escalation_minutes=60,
        min_rest_gap_hours=8
    )
    return soc


@pytest.fixture
def site_a(society_a):
    return Site.objects.create(
        society=society_a,
        name="Site Alpha Main",
        latitude=Decimal("18.520430"),
        longitude=Decimal("73.856740"),
        geofence_radius_m=100,
        max_gps_accuracy_m=50.0,
        pincode="411001",
        area_name="Shivajinagar"
    )


@pytest.fixture
def site_b(society_b):
    return Site.objects.create(
        society=society_b,
        name="Site Beta Main",
        latitude=Decimal("19.076090"),
        longitude=Decimal("72.877426"),
        geofence_radius_m=100,
        max_gps_accuracy_m=50.0,
        pincode="400001",
        area_name="Fort"
    )


@pytest.fixture
def director_user(db):
    return User.objects.create_user(username="director_rep", password="altuspassword123!", role="DIRECTOR")


@pytest.fixture
def supervisor_a(society_a):
    user = User.objects.create_user(username="sup_alpha_rep", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society_a, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def supervisor_b(society_b):
    user = User.objects.create_user(username="sup_beta_rep", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society_b, role="SUPERVISOR", is_active=True)
    return user


def create_worker(username, verification_status='VERIFIED', category='HOUSEKEEPING', home_pincode='', home_area=''):
    user = User.objects.create_user(username=username, password="altuspassword123!", role="WORKER")
    profile = WorkerProfile.objects.create(
        user=user,
        verification_status=verification_status,
        category=category,
        home_pincode=home_pincode,
        home_area=home_area
    )
    return profile


@pytest.mark.django_db
def test_candidate_ranking_exclusions_and_scoring(api_client, society_a, site_a, supervisor_a, kolkata_tz):
    post = Post.objects.create(
        society=society_a, site=site_a, name="Lobby Guard",
        category="HOUSEKEEPING", client_rate=Decimal("500.00")
    )
    shift = Shift.objects.create(
        society=society_a, post=post, name="Morning",
        start_time=time(8, 0), end_time=time(16, 0), required_headcount=1
    )
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(8, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(16, 0)), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=1, status='UNFILLED',
        shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OPEN'
    )

    # 1. Unverified worker -> EXCLUDED
    w_unverified = create_worker("w_unverified", verification_status='PENDING')

    # 2. Worker on approved leave today -> EXCLUDED
    w_leave = create_worker("w_leave", verification_status='VERIFIED')
    LeaveRecord.objects.create(
        society=society_a, worker=w_leave,
        start_date=today, end_date=today,
        status='APPROVED', leave_type='CASUAL'
    )

    # 3. Worker with overlapping shift today -> EXCLUDED
    w_overlap = create_worker("w_overlap", verification_status='VERIFIED')
    DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=2, worker=w_overlap,
        status='SCHEDULED', shift_start_at=start_dt, shift_end_at=end_dt
    )

    # 4. Worker with insufficient rest gap (< 8 hours) -> EXCLUDED
    # Shift ending at 02:00 UTC (6 hours before 08:00 UTC)
    w_rest = create_worker("w_rest", verification_status='VERIFIED')
    DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=3, worker=w_rest,
        status='SCHEDULED',
        shift_start_at=start_dt - timedelta(hours=14),
        shift_end_at=start_dt - timedelta(hours=6)
    )

    # 5. Worker with Home Pincode Match ("411001") -> High Score
    w_pincode_match = create_worker(
        "w_pincode_match", verification_status='VERIFIED',
        category="HOUSEKEEPING", home_pincode="411001", home_area="Shivajinagar"
    )

    # 6. Worker in other area -> Valid candidate, lower score
    w_other_area = create_worker(
        "w_other_area", verification_status='VERIFIED',
        category="OTHER", home_pincode="411099", home_area="Kothrud"
    )

    api_client.force_authenticate(user=supervisor_a)
    url = f"/api/roster/replacements/{rep_req.id}/candidates/"
    res = api_client.get(url)
    assert res.status_code == 200

    candidate_ids = [c["worker_id"] for c in res.data]
    # Verify exclusions
    assert str(w_unverified.id) not in candidate_ids
    assert str(w_leave.id) not in candidate_ids
    assert str(w_overlap.id) not in candidate_ids
    assert str(w_rest.id) not in candidate_ids

    # Verify inclusions
    assert str(w_pincode_match.id) in candidate_ids
    assert str(w_other_area.id) in candidate_ids

    # Verify ranking: pincode & category match worker ranks higher than other area worker
    pincode_cand = next(c for c in res.data if c["worker_id"] == str(w_pincode_match.id))
    other_cand = next(c for c in res.data if c["worker_id"] == str(w_other_area.id))
    assert pincode_cand["score"] > other_cand["score"]
    assert any("Home pincode match" in r for r in pincode_cand["reasons"])


@pytest.mark.django_db
def test_atomic_first_accept_wins_second_gets_409(api_client, society_a, site_a, supervisor_a, kolkata_tz):
    post = Post.objects.create(
        society=society_a, site=site_a, name="Post Concurrency",
        category="HOUSEKEEPING", client_rate=Decimal("400.00")
    )
    shift = Shift.objects.create(
        society=society_a, post=post, name="Day Shift",
        start_time=time(9, 0), end_time=time(17, 0)
    )
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(9, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(17, 0)), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=1, status='UNFILLED',
        shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OPEN'
    )

    w1 = create_worker("worker_one")
    w2 = create_worker("worker_two")

    # Supervisor dispatches offers to both workers
    api_client.force_authenticate(user=supervisor_a)
    dispatch_url = f"/api/roster/replacements/{rep_req.id}/dispatch-offers/"
    res_dispatch = api_client.post(dispatch_url, {"worker_ids": [str(w1.id), str(w2.id)]}, format='json')
    assert res_dispatch.status_code == 200

    offer1 = ReplacementOffer.objects.get(request=rep_req, worker=w1)
    offer2 = ReplacementOffer.objects.get(request=rep_req, worker=w2)

    # Worker 1 accepts -> 200 OK
    api_client.force_authenticate(user=w1.user)
    res_accept1 = api_client.post(f"/api/roster/offers/{offer1.id}/accept/")
    assert res_accept1.status_code == 200
    assert res_accept1.data["status"] == "ACCEPTED"

    # Verify slot is COVERED by w1, req is FILLED, offer2 is WITHDRAWN
    slot.refresh_from_db()
    rep_req.refresh_from_db()
    offer2.refresh_from_db()
    assert slot.status == "COVERED"
    assert slot.covered_by == w1
    assert rep_req.status == "FILLED"
    assert rep_req.filled_by_worker == w1
    assert offer2.status == "WITHDRAWN"

    # Worker 2 attempts to accept -> 409 Conflict (Amendment 3)
    api_client.force_authenticate(user=w2.user)
    res_accept2 = api_client.post(f"/api/roster/offers/{offer2.id}/accept/")
    assert res_accept2.status_code == 409


@pytest.mark.django_db
def test_covered_slot_original_worker_clock_in_returns_409_and_reliever_succeeds(
    api_client, society_a, site_a, supervisor_a, kolkata_tz
):
    """
    Amendment 1: Once a slot is COVERED, original worker's clock-in returns 409;
    replacement worker (covered_by) is permitted to clock in.
    """
    post = Post.objects.create(
        society=society_a, site=site_a, name="Gate 1",
        category="SECURITY", client_rate=Decimal("600.00")
    )
    shift = Shift.objects.create(
        society=society_a, post=post, name="Shift Normal",
        start_time=time(8, 0), end_time=time(16, 0)
    )
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(8, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(16, 0)), kolkata_tz).astimezone(dt_tz.utc)

    orig_worker = create_worker("orig_guard")
    reliever_worker = create_worker("reliever_guard")

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=1, worker=orig_worker,
        covered_by=reliever_worker, status='COVERED',
        shift_start_at=start_dt, shift_end_at=end_dt
    )

    now = timezone.now()
    clock_in_payload = {
        "roster_entry_id": str(slot.id),
        "lat": 18.520430,
        "lng": 73.856740,
        "accuracy": 10.0,
        "clock_in_uuid": str(uuid.uuid4()),
        "client_timestamp": now.isoformat()
    }

    # Original worker attempts clock-in -> 409 Conflict
    api_client.force_authenticate(user=orig_worker.user)
    res_orig = api_client.post("/api/roster/clock-in/", clock_in_payload, format='json')
    assert res_orig.status_code == 409
    assert "replacement" in res_orig.data["error"].lower()

    # Reliever worker clocks in -> 201 Created
    api_client.force_authenticate(user=reliever_worker.user)
    clock_in_payload["clock_in_uuid"] = str(uuid.uuid4())
    res_reliever = api_client.post("/api/roster/clock-in/", clock_in_payload, format='json')
    assert res_reliever.status_code == 201
    assert res_reliever.data["worker"] == reliever_worker.id


@pytest.mark.django_db
def test_cancelling_replacement_restores_original_worker_clock_in(
    api_client, society_a, site_a, supervisor_a, kolkata_tz
):
    """
    Amendment 1: Cancelling replacement restores slot to SCHEDULED and allows
    original worker to clock in.
    """
    post = Post.objects.create(society=society_a, site=site_a, name="Post Cancel", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Day", start_time=time(9, 0), end_time=time(17, 0))
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(9, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(17, 0)), kolkata_tz).astimezone(dt_tz.utc)

    orig_worker = create_worker("orig_w_cancel")
    reliever = create_worker("reliever_cancel")

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift,
        date=today, slot_number=1, worker=orig_worker,
        covered_by=reliever, status='COVERED',
        shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot,
        reason='MANUAL', status='FILLED', filled_by_worker=reliever
    )

    # Cancel replacement request
    api_client.force_authenticate(user=supervisor_a)
    cancel_url = f"/api/roster/replacements/{rep_req.id}/cancel/"
    res_cancel = api_client.post(cancel_url, {"reason": "Original worker is available after all."}, format='json')
    assert res_cancel.status_code == 200

    slot.refresh_from_db()
    assert slot.status == "SCHEDULED"
    assert slot.covered_by is None

    # Original worker can now clock in
    now = timezone.now()
    api_client.force_authenticate(user=orig_worker.user)
    res_clock = api_client.post("/api/roster/clock-in/", {
        "roster_entry_id": str(slot.id),
        "lat": 18.520430,
        "lng": 73.856740,
        "accuracy": 12.0,
        "clock_in_uuid": str(uuid.uuid4()),
        "client_timestamp": now.isoformat()
    }, format='json')
    assert res_clock.status_code == 201


@pytest.mark.django_db
def test_expired_offer_cannot_be_accepted(api_client, society_a, site_a, supervisor_a, kolkata_tz):
    post = Post.objects.create(society=society_a, site=site_a, name="Post Expire", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift E", start_time=time(9, 0), end_time=time(17, 0))
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(9, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(17, 0)), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today,
        slot_number=1, status='UNFILLED', shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OFFERING'
    )
    w = create_worker("worker_expired_offer")

    # Create offer with expiry in the past
    past_expiry = timezone.now() - timedelta(minutes=5)
    offer = ReplacementOffer.objects.create(
        society=society_a, request=rep_req, worker=w,
        status='OFFERED', expires_at=past_expiry
    )

    api_client.force_authenticate(user=w.user)
    res = api_client.post(f"/api/roster/offers/{offer.id}/accept/")
    assert res.status_code == 400
    assert "expired" in res.data["error"].lower()


@pytest.mark.django_db
def test_direct_assign_with_hard_blocks_and_warnings(
    api_client, society_a, site_a, supervisor_a, director_user, kolkata_tz
):
    post = Post.objects.create(society=society_a, site=site_a, name="Post Direct", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift D", start_time=time(9, 0), end_time=time(17, 0))
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(9, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(17, 0)), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today,
        slot_number=1, status='UNFILLED', shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OPEN'
    )

    # 1. Hard block: worker is unverified -> 400
    w_unverified = create_worker("w_unver_direct", verification_status='PENDING')
    api_client.force_authenticate(user=supervisor_a)
    url_assign = f"/api/roster/replacements/{rep_req.id}/direct-assign/"
    res_block = api_client.post(url_assign, {"worker_id": str(w_unverified.id)}, format='json')
    assert res_block.status_code == 400
    assert "hard block" in res_block.data["error"].lower()

    # 2. Worker with warnings (>12h on this date)
    w_busy = create_worker("w_busy_direct", verification_status='VERIFIED')
    # Assign worker to a 6-hour shift on the same day (8 + 6 = 14h > 12h)
    DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today,
        slot_number=2, worker=w_busy, status='SCHEDULED',
        shift_start_at=start_dt - timedelta(hours=14),
        shift_end_at=start_dt - timedelta(hours=8)  # Exactly 8h rest gap, but total 14h working
    )

    # Supervisor attempts direct-assign without acknowledging warnings -> 400
    res_warn = api_client.post(url_assign, {"worker_id": str(w_busy.id)}, format='json')
    assert res_warn.status_code == 400
    assert "acknowledged" in res_warn.data["error"].lower()

    # Supervisor direct-assigns with acknowledge_warnings=True -> 200 OK
    res_ack = api_client.post(url_assign, {
        "worker_id": str(w_busy.id),
        "acknowledge_warnings": True
    }, format='json')
    assert res_ack.status_code == 200
    assert res_ack.data["status"] == "FILLED"

    # Verify AuditLog recorded
    audit = AuditLog.objects.filter(action='DIRECT_ASSIGN_REPLACEMENT', target_id=rep_req.id).first()
    assert audit is not None
    assert str(w_busy.id) == audit.changes["worker_id"]


@pytest.mark.django_db
def test_confirm_by_phone_supervisor_action(api_client, society_a, site_a, supervisor_a, kolkata_tz):
    post = Post.objects.create(society=society_a, site=site_a, name="Post Phone", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift P", start_time=time(9, 0), end_time=time(17, 0))
    today = timezone.localdate()
    start_dt = timezone.make_aware(datetime.combine(today, time(9, 0)), kolkata_tz).astimezone(dt_tz.utc)
    end_dt = timezone.make_aware(datetime.combine(today, time(17, 0)), kolkata_tz).astimezone(dt_tz.utc)

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today,
        slot_number=1, status='UNFILLED', shift_start_at=start_dt, shift_end_at=end_dt
    )
    rep_req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OPEN'
    )
    worker = create_worker("w_phone_confirm")

    api_client.force_authenticate(user=supervisor_a)
    url = f"/api/roster/replacements/{rep_req.id}/confirm-by-phone/"

    # Missing notes -> 400
    res_no_notes = api_client.post(url, {"worker_id": str(worker.id)}, format='json')
    assert res_no_notes.status_code == 400

    # With notes -> 200 OK
    notes_text = "Called worker at 07:30 AM; worker verbally confirmed arrival at 08:45 AM."
    res = api_client.post(url, {"worker_id": str(worker.id), "notes": notes_text}, format='json')
    assert res.status_code == 200
    assert res.data["status"] == "FILLED"

    audit = AuditLog.objects.filter(action='CONFIRM_BY_PHONE', target_id=rep_req.id).first()
    assert audit is not None
    assert audit.reason == notes_text


@pytest.mark.django_db
def test_process_replacements_management_command(society_a, site_a, kolkata_tz):
    post = Post.objects.create(society=society_a, site=site_a, name="Post Cmd", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift Cmd", start_time=time(10, 0), end_time=time(18, 0))
    today = timezone.localdate()
    now = timezone.now()

    # Request 1: Active offer expired in the past -> should expire offer and set req back to OPEN
    start_dt1 = now + timedelta(hours=5)
    end_dt1 = start_dt1 + timedelta(hours=8)
    slot1 = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=1,
        status='UNFILLED', shift_start_at=start_dt1, shift_end_at=end_dt1
    )
    req1 = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot1, reason='UNFILLED', status='OFFERING'
    )
    w1 = create_worker("w_cmd_expired")
    offer1 = ReplacementOffer.objects.create(
        society=society_a, request=req1, worker=w1, status='OFFERED',
        expires_at=now - timedelta(minutes=2)
    )

    # Request 2: Shift starts within 30 minutes (escalation threshold is 60m) -> should ESCALATE
    start_dt2 = now + timedelta(minutes=30)
    end_dt2 = start_dt2 + timedelta(hours=8)
    slot2 = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=2,
        status='UNFILLED', shift_start_at=start_dt2, shift_end_at=end_dt2
    )
    req2 = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot2, reason='UNFILLED', status='OPEN'
    )

    # Run command
    call_command('process_replacements')

    offer1.refresh_from_db()
    req1.refresh_from_db()
    req2.refresh_from_db()

    assert offer1.status == "EXPIRED"
    assert req1.status == "OPEN"
    assert req2.status == "ESCALATED"
    assert req2.escalated_at is not None

    # Verify Alert created for req2
    alert = Alert.objects.filter(roster_entry=slot2, alert_type='UNFILLED').first()
    assert alert is not None
    assert "escalated" in alert.notes.lower()


@pytest.mark.django_db
def test_replacement_metrics_calculation_and_p90(api_client, society_a, site_a, supervisor_a, kolkata_tz):
    """
    Amendment 10: Denominator includes all non-cancelled requests.
    Computes fill-before-shift-start rate and P90 time-to-fill using nearest-rank.
    Hand-calculated values:
      Req A: Cancelled -> Excluded from denominator
      Req B: Opened at 08:00, Shift start at 10:00, Filled at 08:30 (time to fill = 30m, before shift start)
      Req C: Opened at 08:00, Shift start at 08:30, Filled at 09:30 (time to fill = 90m, after shift start)
      Total non-cancelled = 2
      Filled count = 2 (Fill rate = 100.0%)
      Fill before shift start count = 1 (50.0%)
      Avg time to fill = (30 + 90)/2 = 60.0m
      P90 time to fill = 90.0m
    """
    post = Post.objects.create(society=society_a, site=site_a, name="Post Metrics", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift M", start_time=time(10, 0), end_time=time(18, 0))
    today = timezone.localdate()

    w1 = create_worker("w_m1")
    w2 = create_worker("w_m2")

    base_time = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)

    # Req A: CANCELLED
    slot_a = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=1,
        status='SCHEDULED', shift_start_at=base_time + timedelta(hours=2),
        shift_end_at=base_time + timedelta(hours=10)
    )
    ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot_a, reason='MANUAL',
        status='CANCELLED'
    )

    # Req B: Filled 30 mins after open (at 08:30), shift start at 10:00 (before start)
    slot_b = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=2,
        status='COVERED', covered_by=w1, shift_start_at=base_time + timedelta(hours=2),
        shift_end_at=base_time + timedelta(hours=10)
    )
    req_b = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot_b, reason='UNFILLED',
        status='FILLED', filled_by_worker=w1, filled_at=base_time + timedelta(minutes=30)
    )
    ReplacementRequest.objects.filter(id=req_b.id).update(opened_at=base_time)

    # Req C: Filled 90 mins after open (at 09:30), shift start was at 08:30 (after start)
    slot_c = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=3,
        status='COVERED', covered_by=w2, shift_start_at=base_time + timedelta(minutes=30),
        shift_end_at=base_time + timedelta(hours=8)
    )
    req_c = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot_c, reason='UNFILLED',
        status='FILLED', filled_by_worker=w2, filled_at=base_time + timedelta(minutes=90)
    )
    ReplacementRequest.objects.filter(id=req_c.id).update(opened_at=base_time)

    api_client.force_authenticate(user=supervisor_a)
    month_str = today.strftime('%Y-%m')
    res = api_client.get(f"/api/roster/replacements/metrics/?month={month_str}")
    assert res.status_code == 200

    data = res.data
    assert data["total_non_cancelled"] == 2
    assert data["filled_count"] == 2
    assert data["fill_rate_pct"] == 100.0
    assert data["fill_before_shift_start_count"] == 1
    assert data["fill_before_shift_start_pct"] == 50.0
    assert data["avg_time_to_fill_minutes"] == 60.0
    assert data["p90_time_to_fill_minutes"] == 90.0
    assert "nearest_rank" in data["p90_method"]


@pytest.mark.django_db
def test_cross_society_isolation_returns_404(api_client, society_a, society_b, site_a, supervisor_b, kolkata_tz):
    post = Post.objects.create(society=society_a, site=site_a, name="Post Cross", category="HOUSEKEEPING")
    shift = Shift.objects.create(society=society_a, post=post, name="Shift C", start_time=time(9, 0), end_time=time(17, 0))
    today = timezone.localdate()
    now = timezone.now()

    slot = DailyRoster.objects.create(
        society=society_a, post=post, shift=shift, date=today, slot_number=1,
        status='UNFILLED', shift_start_at=now + timedelta(hours=2),
        shift_end_at=now + timedelta(hours=10)
    )
    req = ReplacementRequest.objects.create(
        society=society_a, roster_entry=slot, reason='UNFILLED', status='OPEN'
    )

    # Supervisor from Society B attempts to access Society A's replacement request
    api_client.force_authenticate(user=supervisor_b)

    # Detail -> 404
    res_detail = api_client.get(f"/api/roster/replacements/{req.id}/")
    assert res_detail.status_code == 404

    # Candidates -> 404
    res_cand = api_client.get(f"/api/roster/replacements/{req.id}/candidates/")
    assert res_cand.status_code == 404

    # Dispatch -> 404
    res_dispatch = api_client.post(f"/api/roster/replacements/{req.id}/dispatch-offers/", {"worker_ids": []})
    assert res_dispatch.status_code == 404

    # Cancel -> 404
    res_cancel = api_client.post(f"/api/roster/replacements/{req.id}/cancel/")
    assert res_cancel.status_code == 404
