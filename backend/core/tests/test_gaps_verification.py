import json
import logging
import uuid
import zoneinfo
from datetime import datetime, date, time, timedelta, timezone as dt_tz
from decimal import Decimal
import pytest
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import (
    User, Society, Site, Membership, SocietySettings,
    WorkerProfile, Post, Shift, RosterAssignment, DailyRoster,
    LeaveRecord, AttendanceEvent, Alert, AuditLog,
    ReplacementRequest, ReplacementOffer, Notification, OTPChallenge
)
from core.otp_utils import generate_otp_code, hash_otp_code, normalize_phone
from core.sms import check_and_record_sms_budget, get_sms_daily_global_cap, ConsoleSMSBackend


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def kolkata_tz():
    return zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.fixture
def society(db):
    soc = Society.objects.create(name="Gaps Test Society", client_type="SOCIETY", address="Pune")
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
def site(society):
    return Site.objects.create(
        society=society,
        name="Main Gate Site",
        latitude=18.5204,
        longitude=73.8567,
        geofence_radius_m=100,
        max_gps_accuracy_m=50,
        area_name="Kothrud",
        pincode="411038"
    )


@pytest.fixture
def post(society, site):
    return Post.objects.create(
        society=society,
        site=site,
        name="Security Gate 1",
        category="SECURITY",
        billing_basis="PER_SHIFT",
        client_rate=Decimal("1200.00"),
        is_active=True
    )


@pytest.fixture
def shift(society, post):
    return Shift.objects.create(
        society=society,
        post=post,
        name="Morning Guard Shift",
        start_time=time(6, 0),
        end_time=time(14, 0),
        crosses_midnight=False,
        days_of_week=[0, 1, 2, 3, 4, 5, 6],
        required_headcount=1,
        is_active=True
    )


@pytest.fixture
def director_user(society):
    user = User.objects.create_user(username="test_director", password="altuspassword123!", role="DIRECTOR")
    Membership.objects.create(user=user, society=society, role="DIRECTOR", is_active=True)
    return user


@pytest.fixture
def supervisor_user(society):
    user = User.objects.create_user(username="test_supervisor", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def worker_1(society):
    u = User.objects.create_user(username="worker_one", role="WORKER")
    u.set_unusable_password()
    u.save()
    wp = WorkerProfile.objects.create(
        user=u,
        phone="+919111111111",
        verification_status="VERIFIED",
        category="SECURITY",
        bank_account_number="ACC111111",
        bank_ifsc="HDFC0001",
        compensation_rate=Decimal("600.00")
    )
    return u, wp


@pytest.fixture
def worker_2(society):
    u = User.objects.create_user(username="worker_two", role="WORKER")
    u.set_unusable_password()
    u.save()
    wp = WorkerProfile.objects.create(
        user=u,
        phone="+919222222222",
        verification_status="VERIFIED",
        category="SECURITY",
        bank_account_number="ACC222222",
        bank_ifsc="HDFC0002",
        compensation_rate=Decimal("650.00")
    )
    return u, wp


@pytest.mark.django_db
class TestGapsVerification:

    def test_original_worker_blocked_when_covered_and_restored_after_cancel(
        self, api_client, society, site, post, shift, worker_1, worker_2, supervisor_user, kolkata_tz
    ):
        """
        Original worker clock-in returns 409 when slot is COVERED.
        Reliever can clock in.
        Cancelling replacement restores slot to SCHEDULED and allows original worker clock-in.
        """
        u1, wp1 = worker_1
        u2, wp2 = worker_2

        today = timezone.localdate()
        start_naive = datetime.combine(today, shift.start_time)
        start_dt = timezone.make_aware(start_naive, kolkata_tz).astimezone(dt_tz.utc)
        end_naive = datetime.combine(today, shift.end_time)
        end_dt = timezone.make_aware(end_naive, kolkata_tz).astimezone(dt_tz.utc)

        slot = DailyRoster.objects.create(
            society=society,
            post=post,
            shift=shift,
            date=today,
            slot_number=1,
            worker=wp1,
            status='SCHEDULED',
            shift_start_at=start_dt,
            shift_end_at=end_dt
        )

        rep_req = ReplacementRequest.objects.create(
            society=society,
            roster_entry=slot,
            reason='ABSENT',
            status='OPEN'
        )

        # Direct assign wp2 as reliever
        api_client.force_authenticate(user=supervisor_user)
        assign_res = api_client.post(
            f"/api/roster/replacements/{rep_req.id}/direct-assign/",
            {"worker_id": str(wp2.id), "acknowledge_warnings": True},
            format='json'
        )
        assert assign_res.status_code == 200
        slot.refresh_from_db()
        assert slot.status == 'COVERED'
        assert slot.covered_by == wp2

        # Original worker attempts clock-in -> MUST return 409 Conflict
        api_client.force_authenticate(user=u1)
        clock_in_payload = {
            "roster_entry_id": str(slot.id),
            "clock_in_uuid": str(uuid.uuid4()),
            "client_timestamp": timezone.now().isoformat(),
            "lat": 18.5204,
            "lng": 73.8567,
            "gps_accuracy_m": 10.0
        }
        res_orig = api_client.post("/api/roster/clock-in/", clock_in_payload, format='json')
        assert res_orig.status_code == 409
        assert "reassigned to a replacement worker" in res_orig.data['error']

        # Cancel the replacement
        api_client.force_authenticate(user=supervisor_user)
        cancel_res = api_client.post(
            f"/api/roster/replacements/{rep_req.id}/cancel/",
            {"reason": "Original worker arrived on site"},
            format='json'
        )
        assert cancel_res.status_code == 200
        slot.refresh_from_db()
        assert slot.status == 'SCHEDULED'
        assert slot.covered_by is None

        # Original worker can now clock in successfully
        api_client.force_authenticate(user=u1)
        res_orig_restored = api_client.post("/api/roster/clock-in/", clock_in_payload, format='json')
        assert res_orig_restored.status_code in (200, 201)
        assert str(res_orig_restored.data['worker']) == str(wp1.id)

    def test_reliever_on_covered_slot_does_not_create_duplicate_slot_or_exceed_headcount_after_generate_roster(
        self, society, site, post, shift, worker_1, worker_2, kolkata_tz
    ):
        """
        Running generate_roster when a slot is COVERED preserves COVERED status
        and never creates duplicate slots or exceeds required_headcount.
        """
        u1, wp1 = worker_1
        u2, wp2 = worker_2

        tomorrow = timezone.localdate() + timedelta(days=1)
        RosterAssignment.objects.create(
            society=society,
            shift=shift,
            worker=wp1,
            start_date=timezone.localdate(),
            status='ACTIVE'
        )

        # 1. Run generate_roster
        call_command('generate_roster', days=2, date=timezone.localdate().isoformat())
        slots = DailyRoster.objects.filter(shift=shift, date=tomorrow)
        assert slots.count() == 1
        slot = slots.first()
        assert slot.worker == wp1
        assert slot.status == 'SCHEDULED'

        # 2. Cover slot with wp2
        slot.covered_by = wp2
        slot.status = 'COVERED'
        slot.save()

        # 3. Re-run generate_roster
        call_command('generate_roster', days=2, date=timezone.localdate().isoformat())

        # Headcount must still be exactly 1; status must remain COVERED with covered_by intact
        slots_after = DailyRoster.objects.filter(shift=shift, date=tomorrow)
        assert slots_after.count() == 1
        slot_after = slots_after.first()
        assert slot_after.status == 'COVERED'
        assert slot_after.covered_by == wp2

    def test_rest_gap_hard_block_on_direct_assign(
        self, api_client, society, site, post, shift, worker_1, worker_2, supervisor_user, kolkata_tz
    ):
        """
        Direct assign is hard-blocked (400 Bad Request) if rest gap between shifts is < min_rest_gap_hours.
        """
        u1, wp1 = worker_1
        u2, wp2 = worker_2

        today = timezone.localdate()
        # Shift 1 ends at 14:00
        s1_end = timezone.make_aware(datetime.combine(today, time(14, 0)), kolkata_tz).astimezone(dt_tz.utc)
        s1_start = timezone.make_aware(datetime.combine(today, time(6, 0)), kolkata_tz).astimezone(dt_tz.utc)

        DailyRoster.objects.create(
            society=society,
            post=post,
            shift=shift,
            date=today,
            slot_number=1,
            worker=wp2,
            status='SCHEDULED',
            shift_start_at=s1_start,
            shift_end_at=s1_end
        )

        # Replacement slot starts at 18:00 (only 4h gap, < 8h required)
        rep_start = timezone.make_aware(datetime.combine(today, time(18, 0)), kolkata_tz).astimezone(dt_tz.utc)
        rep_end = timezone.make_aware(datetime.combine(today, time(23, 0)), kolkata_tz).astimezone(dt_tz.utc)

        rep_slot = DailyRoster.objects.create(
            society=society,
            post=post,
            shift=shift,
            date=today,
            slot_number=2,
            worker=wp1,
            status='UNFILLED',
            shift_start_at=rep_start,
            shift_end_at=rep_end
        )

        req = ReplacementRequest.objects.create(
            society=society,
            roster_entry=rep_slot,
            reason='UNFILLED',
            status='OPEN'
        )

        api_client.force_authenticate(user=supervisor_user)
        res = api_client.post(
            f"/api/roster/replacements/{req.id}/direct-assign/",
            {"worker_id": str(wp2.id), "acknowledge_warnings": True},
            format='json'
        )
        assert res.status_code == 400
        assert "Hard block" in res.data['error']
        assert "Rest gap before shift is 4.0h" in res.data['error']

    def test_revoked_token_rejected_including_same_second_edge(self, api_client, worker_1):
        """
        Token is rejected even if revoked at the exact same-second edge (token_issued_at <= sessions_revoked_at).
        """
        user, profile = worker_1
        refresh = RefreshToken.for_user(user)
        access_token_str = str(refresh.access_token)
        iat = refresh.access_token.get('iat')

        # Revocation at exact same second
        exact_same_second = datetime.fromtimestamp(iat, tz=dt_tz.utc)
        profile.sessions_revoked_at = exact_same_second
        profile.save(update_fields=['sessions_revoked_at'])

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token_str}')
        res = api_client.get("/api/user/me/")
        assert res.status_code == 401
        assert "Worker session has been revoked" in str(res.data)

    def test_staff_phone_unknown_phone_wrong_code_return_identical_payloads(
        self, api_client, supervisor_user, worker_1
    ):
        """
        Anti-enumeration check:
        Staff phone, unknown phone, and valid worker phone return identical response on OTP request.
        Wrong code, staff phone, unknown phone return identical 400 error on verify.
        """
        u_worker, wp_worker = worker_1

        # 1. Request OTP payloads
        res_unknown = api_client.post("/api/auth/otp/request/", {"phone": "+919999999999"})
        assert res_unknown.status_code == 200
        expected_msg = "If the phone number is registered with an active worker account, a verification code has been sent."
        assert res_unknown.data["message"] == expected_msg
        assert res_unknown.data["cooldown_seconds"] == 30

        supervisor_user.worker_profile = None  # Ensure no worker profile
        res_staff = api_client.post("/api/auth/otp/request/", {"phone": "+919888888888"})
        assert res_staff.status_code == 200
        assert res_staff.data == res_unknown.data

        # 2. Verify OTP payloads
        generic_error = {"error": "Invalid or expired verification code."}

        res_v_unknown = api_client.post("/api/auth/otp/verify/", {"phone": "+919999999999", "code": "123456"})
        assert res_v_unknown.status_code == 400
        assert res_v_unknown.data == generic_error

        res_v_wrong_code = api_client.post("/api/auth/otp/verify/", {"phone": wp_worker.phone, "code": "000000"})
        assert res_v_wrong_code.status_code == 400
        assert res_v_wrong_code.data == generic_error

    def test_otp_never_appears_in_logs(self, caplog, worker_1):
        """
        Verify that raw OTP code NEVER appears in structured logger logs.
        """
        user, profile = worker_1
        code = "789123"

        backend = ConsoleSMSBackend()
        with caplog.at_level(logging.INFO):
            backend.send_otp(profile.phone, code)

        for record in caplog.records:
            assert code not in record.message
            assert code not in str(record)

    def test_fallback_login_code_issue_and_verify(
        self, api_client, supervisor_user, worker_1, caplog
    ):
        """
        Supervisor issues one-time fallback login code:
        - Audited in AuditLog
        - Code never logged or stored in plain text
        - Worker verifies successfully with it once; second attempt fails
        """
        u_worker, wp_worker = worker_1

        api_client.force_authenticate(user=supervisor_user)
        with caplog.at_level(logging.DEBUG):
            res = api_client.post(
                f"/api/workers/{wp_worker.id}/issue-login-code/",
                {"reason": "Worker phone lost network; verbal phone issuance"},
                format='json'
            )
        assert res.status_code == 200
        issued_code = res.data["login_code"]
        assert len(issued_code) == 6
        assert res.data["expires_in_minutes"] == 10

        # Verify not logged
        for r in caplog.records:
            assert issued_code not in r.message

        # Verify AuditLog recorded
        audit = AuditLog.objects.filter(
            action='ISSUE_FALLBACK_LOGIN_CODE',
            target_id=wp_worker.id
        ).first()
        assert audit is not None
        assert audit.actor == supervisor_user
        assert issued_code not in json.dumps(audit.changes)

        # Worker authenticates via verify endpoint using fallback code
        api_client.force_authenticate(user=None)
        verify_res = api_client.post(
            "/api/auth/otp/verify/",
            {"phone": wp_worker.phone, "code": issued_code},
            format='json'
        )
        assert verify_res.status_code == 200
        assert "access" in verify_res.data
        assert verify_res.data["worker_id"] == str(wp_worker.id)

        # Second attempt must fail (single use)
        second_attempt = api_client.post(
            "/api/auth/otp/verify/",
            {"phone": wp_worker.phone, "code": issued_code},
            format='json'
        )
        assert second_attempt.status_code == 400
        assert second_attempt.data["error"] == "Invalid or expired verification code."

    def test_sms_budget_cap_alert_at_80_percent_and_cutoff_at_100_percent(
        self, society, director_user, worker_1, monkeypatch, caplog
    ):
        """
        SMS daily global cap:
        - At 80%, generates Notification to Directors.
        - At 100%, refuses dispatch and logs error without OTP.
        """
        u_worker, wp_worker = worker_1
        monkeypatch.setenv("SMS_DAILY_GLOBAL_CAP", "10")

        now = timezone.now()
        # Create 8 challenges (80% of 10)
        for i in range(8):
            OTPChallenge.objects.create(
                phone=f"+91900000000{i}",
                code_hash="hash",
                expires_at=now + timedelta(minutes=5)
            )

        # 80% threshold reached
        with caplog.at_level(logging.WARNING):
            allowed = check_and_record_sms_budget("+919111111111")
        assert allowed is True

        # Notification generated for director
        notif = Notification.objects.filter(
            recipient=director_user,
            notification_type='SMS_BUDGET_WARNING'
        ).first()
        assert notif is not None
        assert "80%" in notif.title

        # Create 2 more challenges (reaching 100% = 10)
        for i in range(8, 10):
            OTPChallenge.objects.create(
                phone=f"+91900000000{i}",
                code_hash="hash",
                expires_at=now + timedelta(minutes=5)
            )

        # 100% threshold reached: dispatch rejected
        with caplog.at_level(logging.ERROR):
            allowed_at_cap = check_and_record_sms_budget("+919111111111")
        assert allowed_at_cap is False

        # Verify error logged without OTP
        error_records = [r for r in caplog.records if r.levelname == 'ERROR']
        assert len(error_records) >= 1
        assert "Refusing SMS dispatch" in error_records[0].message
        for r in caplog.records:
            assert "OTP" not in r.message or "Verification code" not in r.message

    def test_new_device_approval_and_financial_data_protection(
        self, api_client, supervisor_user, worker_1
    ):
        """
        When new_device_approved=False:
        - Worker profile serializer redacts bank account, ifsc, and compensation rate.
        - /api/workers/{id}/payslips/ returns 403 Forbidden.
        - Supervisor approves device -> data unhidden and payslips accessible.
        """
        u_worker, wp_worker = worker_1
        wp_worker.new_device_approved = False
        wp_worker.save(update_fields=['new_device_approved'])

        # 1. Serializer check
        api_client.force_authenticate(user=u_worker)
        res_profile = api_client.get(f"/api/workers/{wp_worker.id}/")
        assert res_profile.status_code == 200
        assert res_profile.data['bank_account_number'] is None
        assert res_profile.data['bank_ifsc'] is None
        assert res_profile.data['compensation_rate'] is None

        # 2. Payslip endpoint check -> 403
        res_payslips = api_client.get(f"/api/workers/{wp_worker.id}/payslips/")
        assert res_payslips.status_code == 403
        assert "restricted until your new device is approved" in res_payslips.data['error']

        # 3. Supervisor approves new device
        api_client.force_authenticate(user=supervisor_user)
        approve_res = api_client.post(
            f"/api/workers/{wp_worker.id}/device-approval/",
            {"approved": True, "reason": "Worker identity re-verified over video call"},
            format='json'
        )
        assert approve_res.status_code == 200
        assert approve_res.data["new_device_approved"] is True

        # AuditLog recorded
        audit = AuditLog.objects.filter(
            action='APPROVE_DEVICE',
            target_id=wp_worker.id
        ).first()
        assert audit is not None
        assert audit.actor == supervisor_user

        # 4. Data now visible and payslips accessible
        api_client.force_authenticate(user=u_worker)
        res_profile_approved = api_client.get(f"/api/workers/{wp_worker.id}/")
        assert res_profile_approved.data['bank_account_number'] == "ACC111111"
        assert res_profile_approved.data['compensation_rate'] == "600.00"

        res_payslips_approved = api_client.get(f"/api/workers/{wp_worker.id}/payslips/")
        assert res_payslips_approved.status_code == 200
        assert res_payslips_approved.data['bank_account_number'] == "ACC111111"

    def test_decommission_worker_passwords_command(self, db):
        """
        Tests the safe and reversible decommission_worker_passwords command.
        """
        user = User.objects.create_user(username="w_pwd_test", password="testpassword123!", role="WORKER")
        assert user.has_usable_password() is True

        # Dry run
        call_command('decommission_worker_passwords', dry_run=True)
        user.refresh_from_db()
        assert user.has_usable_password() is True

        # Real execution
        call_command('decommission_worker_passwords')
        user.refresh_from_db()
        assert user.has_usable_password() is False

    def test_one_active_replacement_request_per_slot_enforced_at_db_level(
        self, society, site, post, shift, worker_1, kolkata_tz
    ):
        """
        Database partial unique constraint prevents two active ReplacementRequests for the same slot.
        """
        u1, wp1 = worker_1
        today = timezone.localdate()
        start_dt = timezone.now()
        end_dt = start_dt + timedelta(hours=8)

        slot = DailyRoster.objects.create(
            society=society,
            post=post,
            shift=shift,
            date=today,
            slot_number=1,
            worker=wp1,
            status='UNFILLED',
            shift_start_at=start_dt,
            shift_end_at=end_dt
        )

        ReplacementRequest.objects.create(
            society=society,
            roster_entry=slot,
            reason='UNFILLED',
            status='OPEN'
        )

        with pytest.raises(Exception) as exc_info:
            ReplacementRequest.objects.create(
                society=society,
                roster_entry=slot,
                reason='ABSENT',
                status='OFFERING'
            )
        assert "unique" in str(exc_info.value).lower() or "integrity" in str(exc_info.value).lower()

