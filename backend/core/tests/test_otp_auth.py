import time
import uuid
from datetime import datetime, timedelta, timezone as dt_tz
import pytest
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import User, WorkerProfile, OTPChallenge, Society, SocietySettings, Membership
from core.otp_utils import hash_otp_code, verify_otp_code, normalize_phone


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def society(db):
    soc = Society.objects.create(name="OTP Test Society", client_type="SOCIETY", address="Pune")
    SocietySettings.objects.create(society=soc)
    return soc


@pytest.fixture
def director_user(db):
    return User.objects.create_user(username="director_otp", password="altuspassword123!", role="DIRECTOR")


@pytest.fixture
def supervisor_user(society):
    user = User.objects.create_user(username="sup_otp", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=user, society=society, role="SUPERVISOR", is_active=True)
    return user


@pytest.fixture
def worker_user(db):
    user = User.objects.create_user(
        username="worker_otp_test",
        role="WORKER"
    )
    # Amendment 16: Zero default/demo passwords; worker accounts use unusable password
    user.set_unusable_password()
    user.save()

    profile = WorkerProfile.objects.create(
        user=user,
        phone="+919876543210",
        verification_status="VERIFIED",
        category="HOUSEKEEPING"
    )
    return user, profile


@pytest.mark.django_db
def test_valid_otp_login_flow(api_client, worker_user):
    user, profile = worker_user
    phone = "+919876543210"

    # 1. Request OTP
    with patch('core.views_otp.send_otp_async') as mock_send_sms:
        res_req = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res_req.status_code == 200
        assert "message" in res_req.data
        assert res_req.data["cooldown_seconds"] == 30
        assert mock_send_sms.called

        # Extract code from call args
        called_phone, called_code = mock_send_sms.call_args[0]
        assert called_phone == phone
        assert len(called_code) == 6

    # 2. Challenge created with HMAC hash
    challenge = OTPChallenge.objects.filter(phone=phone).first()
    assert challenge is not None
    assert verify_otp_code(phone, called_code, challenge.code_hash)

    # 3. Verify OTP
    res_verify = api_client.post("/api/auth/otp/verify/", {
        "phone": phone,
        "code": called_code,
        "device_id": "device-uuid-1"
    }, format='json')
    assert res_verify.status_code == 200
    assert "access" in res_verify.data
    assert "refresh" in res_verify.data
    assert res_verify.data["username"] == user.username

    # 4. Authenticate request using issued JWT token
    access_token = res_verify.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    res_me = api_client.get("/api/user/me/")
    assert res_me.status_code == 200
    assert res_me.data["username"] == user.username


@pytest.mark.django_db
def test_anti_enumeration_unknown_phone_and_staff_account(api_client, supervisor_user):
    """
    Amendment 11: Identical responses for staff phone and unknown phone;
    send SMS only to registered worker phones.
    """
    with patch('core.views_otp.send_otp_async') as mock_send_sms:
        # Unknown phone
        res_unknown = api_client.post("/api/auth/otp/request/", {"phone": "+919999999999"}, format='json')
        assert res_unknown.status_code == 200
        assert "message" in res_unknown.data
        assert res_unknown.data["cooldown_seconds"] == 30
        assert not mock_send_sms.called
        assert not OTPChallenge.objects.filter(phone="+919999999999").exists()

        # Staff phone (Supervisor)
        supervisor_user.phone_number = "+919888888888"
        supervisor_user.save()
        res_staff = api_client.post("/api/auth/otp/request/", {"phone": "+919888888888"}, format='json')
        assert res_staff.status_code == 200
        assert res_staff.data == res_unknown.data  # Exactly identical payload!
        assert not mock_send_sms.called
        assert not OTPChallenge.objects.filter(phone="+919888888888").exists()


@pytest.mark.django_db
def test_resend_cooldown_30s(api_client, worker_user):
    user, profile = worker_user
    phone = "+919876543210"

    with patch('core.views_otp.send_otp_async'):
        # First request succeeds
        res1 = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res1.status_code == 200

        # Immediate second request returns 429
        res2 = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res2.status_code == 429
        assert "wait" in res2.data["error"].lower()
        assert res2.data["cooldown_seconds"] <= 30


@pytest.mark.django_db
def test_invalid_code_and_lockout_after_5_attempts(api_client, worker_user):
    user, profile = worker_user
    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, valid_code = mock_send.call_args[0]

    # Attempt 1 to 4 with incorrect code -> 400
    for i in range(1, 5):
        res_fail = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": "000000"}, format='json')
        assert res_fail.status_code == 400
        assert "invalid" in res_fail.data["error"].lower()

    # Attempt 5 -> lock out
    res_fail5 = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": "000000"}, format='json')
    assert res_fail5.status_code == 400

    # Attempt 6 (even with valid code) -> Locked out!
    res_locked = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": valid_code}, format='json')
    assert res_locked.status_code == 400
    assert "locked" in res_locked.data["error"].lower()


@pytest.mark.django_db
def test_expired_code_rejected(api_client, worker_user):
    user, profile = worker_user
    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, valid_code = mock_send.call_args[0]

    # Manually expire the challenge
    OTPChallenge.objects.filter(phone=phone).update(expires_at=timezone.now() - timedelta(minutes=1))

    res = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": valid_code}, format='json')
    assert res.status_code == 400
    assert "invalid or expired" in res.data["error"].lower()


@pytest.mark.django_db
def test_code_reuse_rejected_atomic_consumption(api_client, worker_user):
    """
    Amendment 13: Consumption is atomic. Challenge cannot be consumed twice.
    """
    user, profile = worker_user
    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, valid_code = mock_send.call_args[0]

    # First consumption succeeds
    res1 = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": valid_code}, format='json')
    assert res1.status_code == 200

    # Second consumption with same code fails immediately
    res2 = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": valid_code}, format='json')
    assert res2.status_code == 400
    assert "invalid or expired" in res2.data["error"].lower()


@pytest.mark.django_db
def test_newest_challenge_valid_only(api_client, worker_user):
    """
    Amendment 13: Only the newest challenge is valid.
    """
    user, profile = worker_user
    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, code1 = mock_send.call_args[0]

    # Bypass cooldown by updating created_at on challenge 1
    OTPChallenge.objects.filter(phone=phone).update(created_at=timezone.now() - timedelta(seconds=35))

    with patch('core.views_otp.send_otp_async') as mock_send:
        res2 = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res2.status_code == 200
        assert mock_send.called
        _, code2 = mock_send.call_args[0]

    # Code 1 must now fail
    res_code1 = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": code1}, format='json')
    assert res_code1.status_code == 400

    # Code 2 succeeds
    res_code2 = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": code2}, format='json')
    assert res_code2.status_code == 200


@pytest.mark.django_db
def test_session_revocation_rejects_tokens(api_client, worker_user, director_user):
    """
    Amendment 14: Authentication checks token issue time against sessions_revoked_at.
    """
    user, profile = worker_user
    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, code = mock_send.call_args[0]

    res_login = api_client.post("/api/auth/otp/verify/", {"phone": phone, "code": code}, format='json')
    assert res_login.status_code == 200
    access_token = res_login.data["access"]

    # Request works before revocation
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    res_before = api_client.get("/api/user/me/")
    assert res_before.status_code == 200

    # Fast forward clock slightly so revoked_at is after token iat
    time.sleep(1.05)

    # Director revokes sessions using a separate director client
    director_client = APIClient()
    director_client.force_authenticate(user=director_user)
    revoke_url = f"/api/workers/{profile.id}/revoke-sessions/"
    res_revoke = director_client.post(revoke_url, {"reason": "Lost phone report."}, format='json')
    assert res_revoke.status_code == 200

    # Subsequent request using old access token MUST be rejected with 401
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    res_after = api_client.get("/api/user/me/")
    assert res_after.status_code == 401
    assert "revoked" in str(res_after.data).lower()


@pytest.mark.django_db
def test_suspended_worker_rejected(api_client, worker_user):
    """
    Amendment 14: Authentication rejects inactive, suspended or exited workers on every request.
    """
    user, profile = worker_user
    profile.verification_status = "SUSPENDED"
    profile.save()

    phone = "+919876543210"
    with patch('core.views_otp.send_otp_async') as mock_send:
        # OTP request returns generic 200 but sends no SMS
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert not mock_send.called


@pytest.mark.django_db
def test_device_id_change_flagged(api_client, worker_user):
    """
    Amendment 15: Flag new device for supervisor review if device_id changes;
    do not block login.
    """
    user, profile = worker_user
    profile.device_id = "initial-device-123"
    profile.new_device_approved = True
    profile.save()

    phone = "+919876543210"
    OTPChallenge.objects.filter(phone=phone).delete()

    with patch('core.views_otp.send_otp_async') as mock_send:
        res = api_client.post("/api/auth/otp/request/", {"phone": phone}, format='json')
        assert res.status_code == 200
        assert mock_send.called
        _, code = mock_send.call_args[0]

    # Worker logs in from new device
    res = api_client.post("/api/auth/otp/verify/", {
        "phone": phone,
        "code": code,
        "device_id": "new-device-999"
    }, format='json')

    assert res.status_code == 200
    assert res.data["new_device_detected"] is True
    assert res.data["new_device_approved"] is False

    profile.refresh_from_db()
    assert profile.device_id == "new-device-999"
    assert profile.new_device_approved is False


@pytest.mark.django_db
def test_worker_accounts_use_unusable_passwords(api_client, worker_user):
    """
    Amendment 16: Zero default/demo passwords; worker accounts use unusable password.
    Password login endpoint must reject workers attempting password authentication.
    """
    user, profile = worker_user
    assert not user.has_usable_password()

    # Attempt standard password login
    res = api_client.post("/api/auth/login/", {
        "username": user.username,
        "password": "altuspassword123!"
    }, format='json')
    assert res.status_code == 401
