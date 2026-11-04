import os
import uuid
from datetime import datetime, time, timedelta, timezone as dt_tz
from unittest import mock
import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    User, WorkerProfile, Society, Site, Post, Shift,
    DailyRoster, RosterAssignment, OTPChallenge, AuditLog, Membership
)
from core.security_checks import validate_production_settings
from core.otp_utils import generate_otp_code, hash_otp_code


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def society_alpha(db):
    s = Society.objects.create(name="Alpha Society")
    Site.objects.create(society=s, name="Alpha Site", latitude=18.5204, longitude=73.8567, geofence_radius_m=200)
    return s


@pytest.fixture
def society_beta(db):
    s = Society.objects.create(name="Beta Society")
    Site.objects.create(society=s, name="Beta Site", latitude=19.0760, longitude=72.8777, geofence_radius_m=200)
    return s


@pytest.fixture
def worker_1(db):
    u = User.objects.create_user(username="worker_db_1", password="altuspassword123!", role="WORKER")
    wp = WorkerProfile.objects.create(user=u, phone="+919876543210", verification_status="VERIFIED")
    return u, wp


@pytest.fixture
def worker_2(db):
    u = User.objects.create_user(username="worker_db_2", password="altuspassword123!", role="WORKER")
    wp = WorkerProfile.objects.create(user=u, phone="+919876543211", verification_status="VERIFIED")
    return u, wp


@pytest.fixture
def supervisor_alpha(db, society_alpha):
    u = User.objects.create_user(username="sup_alpha", password="altuspassword123!", role="SUPERVISOR")
    Membership.objects.create(user=u, society=society_alpha, role="SUPERVISOR", is_active=True)
    return u


@pytest.fixture
def director_user(db):
    return User.objects.create_user(username="director_corp", password="altuspassword123!", role="DIRECTOR")


# ── Item D: Deploy Blockers Tests ─────────────────────────────────────────────

@pytest.mark.django_db
class TestDeployBlockers:

    def test_debug_defaults_to_false(self):
        """1. DEBUG defaults to False (test fails if True)."""
        assert settings.DEBUG is False, "CRITICAL: DEBUG must default to False in production!"

    def test_startup_fails_when_database_url_missing(self):
        """With DEBUG=False, startup fails if DATABASE_URL missing."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='a' * 32,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC123',
                TWILIO_AUTH_TOKEN='tok123',
                TWILIO_PHONE_NUMBER='+1555',
                OTP_HMAC_SECRET='otp-secret-long-enough',
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "DATABASE_URL is missing" in str(exc_info.value)

    def test_startup_fails_when_database_not_postgresql(self):
        """With DEBUG=False, startup fails if database is not PostgreSQL."""
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///db.sqlite3'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='a' * 32,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC123',
                TWILIO_AUTH_TOKEN='tok123',
                TWILIO_PHONE_NUMBER='+1555',
                OTP_HMAC_SECRET='otp-secret-long-enough',
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "database engine is not PostgreSQL" in str(exc_info.value)

    def test_startup_fails_when_otp_hmac_secret_missing(self):
        """With DEBUG=False, startup fails if OTP_HMAC_SECRET is missing."""
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@localhost:5432/db'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='a' * 32,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC123',
                TWILIO_AUTH_TOKEN='tok123',
                TWILIO_PHONE_NUMBER='+1555',
                OTP_HMAC_SECRET='',
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "OTP_HMAC_SECRET is missing" in str(exc_info.value)

    def test_startup_fails_when_otp_hmac_secret_falls_back_to_secret_key(self):
        """With DEBUG=False, OTP_HMAC_SECRET cannot be identical to SECRET_KEY (no fallback)."""
        sec = 'very-secure-key-used-for-django-secret-key-at-least-32!'
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@localhost:5432/db'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY=sec,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC123',
                TWILIO_AUTH_TOKEN='tok123',
                TWILIO_PHONE_NUMBER='+1555',
                OTP_HMAC_SECRET=sec,
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "using SECRET_KEY" in str(exc_info.value)

    def test_startup_fails_when_redis_url_missing(self):
        """With DEBUG=False, startup fails if REDIS_URL missing."""
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@localhost:5432/db'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='a' * 32,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC123',
                TWILIO_AUTH_TOKEN='tok123',
                TWILIO_PHONE_NUMBER='+1555',
                OTP_HMAC_SECRET='dedicated-otp-secret-key-32chars!!',
                REDIS_URL='',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "REDIS_URL is missing" in str(exc_info.value)

    def test_startup_fails_when_sms_credentials_missing(self):
        """With DEBUG=False, startup fails if Twilio/AWS credentials missing."""
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@localhost:5432/db'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='a' * 32,
                ALLOWED_HOSTS=['altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='',
                TWILIO_AUTH_TOKEN='',
                TWILIO_PHONE_NUMBER='',
                OTP_HMAC_SECRET='dedicated-otp-secret-key-32chars!!',
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}}
            ):
                with pytest.raises(ImproperlyConfigured) as exc_info:
                    validate_production_settings()
                assert "SMS provider credentials missing" in str(exc_info.value)

    def test_supervisor_scoped_issue_login_code(
        self, api_client, society_alpha, society_beta, supervisor_alpha, director_user, worker_1, worker_2
    ):
        """
        issue-login-code:
        - Supervisors only for workers on rosters of their own societies (cross-society returns 403).
        - Directors any worker.
        - Requires non-empty reason (returns 400 if missing).
        - Max 3 per worker per day (returns 429 on 4th).
        - Sends SMS to worker when issued.
        - Writes AuditLog entry.
        """
        with override_settings(OTP_HMAC_SECRET="test-otp-secret-key-32chars!!"):
            u1, wp1 = worker_1
            u2, wp2 = worker_2

            site_a = society_alpha.sites.first()
            post_a = Post.objects.create(society=society_alpha, site=site_a, name="Alpha HK Post")
            shift_a = Shift.objects.create(society=society_alpha, post=post_a, name="Morn", start_time=time(8, 0), end_time=time(16, 0))

            # Worker 1 is on roster of Alpha Society
            DailyRoster.objects.create(
                society=society_alpha, post=post_a, shift=shift_a,
                date=timezone.localdate(), slot_number=1, worker=wp1, status='SCHEDULED',
                shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8)
            )

            # Worker 2 is on roster of Beta Society (cross-society from Alpha)
            site_b = society_beta.sites.first()
            post_b = Post.objects.create(society=society_beta, site=site_b, name="Beta HK Post")
            shift_b = Shift.objects.create(society=society_beta, post=post_b, name="Morn B", start_time=time(8, 0), end_time=time(16, 0))
            DailyRoster.objects.create(
                society=society_beta, post=post_b, shift=shift_b,
                date=timezone.localdate(), slot_number=1, worker=wp2, status='SCHEDULED',
                shift_start_at=timezone.now(), shift_end_at=timezone.now() + timedelta(hours=8)
            )

            # 1. Supervisor Alpha attempts for Worker 2 (cross-society / not on supervisor's roster) -> 403 Forbidden
            api_client.force_authenticate(user=supervisor_alpha)
            res_cross = api_client.post(
                f"/api/workers/{wp2.id}/issue-login-code/",
                {"reason": "Worker 2 forgot device"},
                format='json'
            )
            assert res_cross.status_code == 403
            assert "within their assigned societies" in res_cross.data['error']

            # 2. Supervisor Alpha missing reason -> 400 Bad Request
            res_noreason = api_client.post(
                f"/api/workers/{wp1.id}/issue-login-code/",
                {"reason": ""},
                format='json'
            )
            assert res_noreason.status_code == 400
            assert "reason is required" in res_noreason.data['error']

            # 3. Supervisor Alpha successfully issues code for Worker 1
            with mock.patch('core.views_otp.send_otp_async') as mock_sms:
                res_ok1 = api_client.post(
                    f"/api/workers/{wp1.id}/issue-login-code/",
                    {"reason": "Phone damaged, temporary phone"},
                    format='json'
                )
                assert res_ok1.status_code == 200
                assert "login_code" in res_ok1.data
                assert res_ok1.data['expires_in_minutes'] == 10
                mock_sms.assert_called_once_with(wp1.phone, res_ok1.data['login_code'])

            # Verify AuditLog created
            assert AuditLog.objects.filter(
                actor=supervisor_alpha,
                target_id=wp1.id,
                action='ISSUE_FALLBACK_LOGIN_CODE',
                reason="Phone damaged, temporary phone"
            ).exists() is True

            # 4. Director can issue for Worker 2 (any worker permitted)
            api_client.force_authenticate(user=director_user)
            with mock.patch('core.views_otp.send_otp_async') as mock_sms:
                res_dir = api_client.post(
                    f"/api/workers/{wp2.id}/issue-login-code/",
                    {"reason": "Director authorization for new recruit"},
                    format='json'
                )
                assert res_dir.status_code == 200
                assert "login_code" in res_dir.data
                mock_sms.assert_called_once_with(wp2.phone, res_dir.data['login_code'])

            # 5. Daily limit: Max 3 per worker per day
            api_client.force_authenticate(user=supervisor_alpha)
            # We already issued 1 for worker 1. Issue 2nd and 3rd:
            res_ok2 = api_client.post(f"/api/workers/{wp1.id}/issue-login-code/", {"reason": "Reason 2"}, format='json')
            assert res_ok2.status_code == 200
            res_ok3 = api_client.post(f"/api/workers/{wp1.id}/issue-login-code/", {"reason": "Reason 3"}, format='json')
            assert res_ok3.status_code == 200

            # 4th issue in same day fails with 429 Too Many Requests
            res_ok4 = api_client.post(f"/api/workers/{wp1.id}/issue-login-code/", {"reason": "Reason 4"}, format='json')
            assert res_ok4.status_code == 429
            assert "Maximum daily limit of 3 fallback login codes reached" in res_ok4.data['error']

    def test_worker_first_device_auto_approved_and_second_device_requires_approval(
        self, api_client, worker_1
    ):
        """
        Worker's first device is auto-approved; only later device change sets new_device_approved=False.
        """
        u1, wp1 = worker_1
        assert wp1.device_id is None

        # Request OTP
        code = "123456"
        with mock.patch('core.views_otp.send_otp_async'), override_settings(OTP_HMAC_SECRET="test-otp-secret-key-32chars!!"):
            c_hash = hash_otp_code(wp1.phone, code)
            OTPChallenge.objects.create(
                phone=wp1.phone,
                code_hash=c_hash,
                device_id='dev_phone_1',
                expires_at=timezone.now() + timedelta(minutes=5)
            )

            # 1. First login with dev_phone_1 -> auto-approved
            res_first = api_client.post(
                "/api/auth/otp/verify/",
                {"phone": wp1.phone, "code": code, "device_id": "dev_phone_1"},
                format='json'
            )
            assert res_first.status_code == 200
            assert res_first.data['new_device_detected'] is False
            assert res_first.data['new_device_approved'] is True

            wp1.refresh_from_db()
            assert wp1.device_id == "dev_phone_1"
            assert wp1.new_device_approved is True

            # 2. Second login with different device dev_phone_2 -> requires approval (False)
            code2 = "654321"
            c_hash2 = hash_otp_code(wp1.phone, code2)
            OTPChallenge.objects.create(
                phone=wp1.phone,
                code_hash=c_hash2,
                device_id='dev_phone_2',
                expires_at=timezone.now() + timedelta(minutes=5)
            )

            res_second = api_client.post(
                "/api/auth/otp/verify/",
                {"phone": wp1.phone, "code": code2, "device_id": "dev_phone_2"},
                format='json'
            )
            assert res_second.status_code == 200
            assert res_second.data['new_device_detected'] is True
            assert res_second.data['new_device_approved'] is False

            wp1.refresh_from_db()
            assert wp1.device_id == "dev_phone_2"
            assert wp1.new_device_approved is False
