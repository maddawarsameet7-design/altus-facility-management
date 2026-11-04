"""
core/tests/test_login_security.py

Hardening and security regression tests for authentication:
1. Valid credentials login (200 OK with tokens).
2. Wrong password returns 401 Unauthorized.
3. Throttle returns 429 after limit in production settings with Retry-After header.
4. Dual-layer throttling: username-based throttling blocks credential stuffing across multiple IPs.
5. Seed script refuses to execute when DEBUG=False (raises CommandError).
6. CORS header is absent for untrusted origins when DEBUG=False.
"""
import os
import pytest
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient
from core.models import User
from core.security_checks import validate_production_settings


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Ensure cache is empty before each test so throttle counters start fresh."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def test_user(db):
    user = User.objects.create_user(
        username='security_test_user',
        password='ValidPassword123!',
        email='sec@test.com',
        role='MEMBER'
    )
    return user


@pytest.mark.django_db
class TestLoginSecurity:

    def test_login_works_with_correct_credentials(self, client, test_user):
        """Valid credentials return 200 with JWT access and refresh tokens."""
        url = reverse('token_obtain_pair')
        response = client.post(url, {
            'username': 'security_test_user',
            'password': 'ValidPassword123!'
        }, format='json')

        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_wrong_password_returns_401(self, client, test_user):
        """Invalid credentials return 401 Unauthorized."""
        url = reverse('token_obtain_pair')
        response = client.post(url, {
            'username': 'security_test_user',
            'password': 'WrongPassword999!'
        }, format='json')

        assert response.status_code == 401
        assert 'access' not in response.data

    @override_settings(
        DEBUG=False,
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': (
                'rest_framework_simplejwt.authentication.JWTAuthentication',
            ),
            'DEFAULT_PERMISSION_CLASSES': (
                'rest_framework.permissions.IsAuthenticated',
            ),
            'DEFAULT_THROTTLE_CLASSES': [
                'rest_framework.throttling.AnonRateThrottle',
                'rest_framework.throttling.UserRateThrottle',
            ],
            'DEFAULT_THROTTLE_RATES': {
                'anon': '20/min',
                'user': '200/min',
                'login': '2/min',
                'login_user_ip': '2/min',
                'login_ip': '10/min',
                'login_user': '20/hour',
                'token_refresh': '60/min',
            },
        }
    )
    def test_throttle_returns_429_after_limit_in_production(self, client, test_user):
        """In production throttling (2/min), third request returns 429 with Retry-After header."""
        url = reverse('token_obtain_pair')

        # First request: OK (or 401 for wrong pass)
        r1 = client.post(url, {'username': 'security_test_user', 'password': 'bad'}, format='json')
        assert r1.status_code == 401

        # Second request: OK (or 401)
        r2 = client.post(url, {'username': 'security_test_user', 'password': 'bad'}, format='json')
        assert r2.status_code == 401

        # Third request: Must be throttled with 429
        r3 = client.post(url, {'username': 'security_test_user', 'password': 'bad'}, format='json')
        assert r3.status_code == 429
        # Check Retry-After header is populated
        assert 'Retry-After' in r3.headers or 'retry-after' in r3.headers

    @override_settings(
        DEBUG=False,
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': (
                'rest_framework_simplejwt.authentication.JWTAuthentication',
            ),
            'DEFAULT_PERMISSION_CLASSES': (
                'rest_framework.permissions.IsAuthenticated',
            ),
            'DEFAULT_THROTTLE_RATES': {
                'login_user_ip': '5/min',
                'login_ip': '30/min',
                'login_user': '20/hour',
            },
        }
    )
    def test_attacker_on_ip_a_cannot_lock_out_legitimate_user_on_ip_b(self, client, test_user):
        """Attacker on IP A failing 5 times gets blocked, but legitimate user on IP B can still log in."""
        url = reverse('token_obtain_pair')
        ip_a = '198.51.100.1'
        ip_b = '198.51.100.2'

        # Attacker on IP A fails 5 times
        for _ in range(5):
            res = client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                              REMOTE_ADDR=ip_a, format='json')
            assert res.status_code == 401

        # Attacker's 6th attempt from IP A is throttled (429)
        attacker_blocked = client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                                       REMOTE_ADDR=ip_a, format='json')
        assert attacker_blocked.status_code == 429

        # Legitimate user on IP B logs in with correct password -> SUCCESS (200 OK)
        user_res = client.post(url, {'username': 'security_test_user', 'password': 'ValidPassword123!'},
                               REMOTE_ADDR=ip_b, format='json')
        assert user_res.status_code == 200
        assert 'access' in user_res.data
        assert 'refresh' in user_res.data

    @override_settings(
        DEBUG=False,
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': (
                'rest_framework_simplejwt.authentication.JWTAuthentication',
            ),
            'DEFAULT_PERMISSION_CLASSES': (
                'rest_framework.permissions.IsAuthenticated',
            ),
            'DEFAULT_THROTTLE_RATES': {
                'login_user_ip': '2/min',
                'login_ip': '5/min',
                'token_refresh': '60/min',
            },
        }
    )
    def test_token_refresh_not_blocked_by_login_failures(self, client, test_user):
        """Token refresh endpoint uses its own loose scope and is not blocked by login brute-force limits."""
        login_url = reverse('token_obtain_pair')
        refresh_url = reverse('token_refresh')

        # First obtain a valid refresh token
        login_res = client.post(login_url, {
            'username': 'security_test_user',
            'password': 'ValidPassword123!'
        }, format='json')
        assert login_res.status_code == 200
        refresh_token = login_res.data['refresh']

        # Now spam login with bad credentials until 429
        for _ in range(3):
            client.post(login_url, {'username': 'security_test_user', 'password': 'bad'}, format='json')

        blocked_login = client.post(login_url, {'username': 'security_test_user', 'password': 'bad'}, format='json')
        assert blocked_login.status_code == 429

        # Refresh endpoint remains fully functional and succeeds
        refresh_res = client.post(refresh_url, {'refresh': refresh_token}, format='json')
        assert refresh_res.status_code == 200
        assert 'access' in refresh_res.data

    @override_settings(
        DEBUG=False,
        NUM_PROXIES=1,
        REST_FRAMEWORK={
            'NUM_PROXIES': 1,
            'DEFAULT_THROTTLE_RATES': {
                'login_user_ip': '2/min',
            },
        }
    )
    def test_proxy_ip_x_forwarded_for_resolution(self, client, test_user):
        """X-Forwarded-For is correctly used behind a reverse proxy when NUM_PROXIES is configured."""
        url = reverse('token_obtain_pair')

        # 2 bad attempts from client IP 203.0.113.50 behind proxy 10.0.0.1
        client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                    HTTP_X_FORWARDED_FOR='203.0.113.50', REMOTE_ADDR='10.0.0.1', format='json')
        client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                    HTTP_X_FORWARDED_FOR='203.0.113.50', REMOTE_ADDR='10.0.0.1', format='json')

        # 3rd attempt from 203.0.113.50 is throttled
        blocked = client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                              HTTP_X_FORWARDED_FOR='203.0.113.50', REMOTE_ADDR='10.0.0.1', format='json')
        assert blocked.status_code == 429

        # Different client IP 203.0.113.99 behind the same proxy 10.0.0.1 is NOT throttled
        other = client.post(url, {'username': 'security_test_user', 'password': 'bad'},
                            HTTP_X_FORWARDED_FOR='203.0.113.99', REMOTE_ADDR='10.0.0.1', format='json')
        assert other.status_code == 401

    def test_seed_script_refuses_to_run_when_debug_false(self):
        """seed_data command must refuse to run and raise CommandError if DEBUG is False."""
        with override_settings(DEBUG=False):
            with pytest.raises(CommandError) as exc_info:
                call_command('seed_data')
            assert "Refusing to execute seed_data in production (DEBUG=False)" in str(exc_info.value)

    @override_settings(
        DEBUG=False,
        CORS_ALLOW_ALL_ORIGINS=False,
        CORS_ALLOWED_ORIGINS=['https://altsan.com']
    )
    def test_cors_header_absent_for_unknown_origin_when_debug_false(self, client):
        """When DEBUG=False, requests from untrusted origins do NOT get Access-Control-Allow-Origin."""
        url = reverse('token_obtain_pair')
        # Untrusted origin
        response = client.post(
            url,
            {'username': 'test', 'password': 'bad'},
            HTTP_ORIGIN='https://evil-unauthorized.com',
            format='json'
        )
        assert 'Access-Control-Allow-Origin' not in response.headers
        assert response.headers.get('Access-Control-Allow-Origin') != 'https://evil-unauthorized.com'
        assert response.headers.get('Access-Control-Allow-Origin') != '*'

        # Trusted origin gets proper CORS header and exposes Retry-After
        trusted_response = client.post(
            url,
            {'username': 'test', 'password': 'bad'},
            HTTP_ORIGIN='https://altsan.com',
            format='json'
        )
        assert trusted_response.headers.get('Access-Control-Allow-Origin') == 'https://altsan.com'
        assert 'Retry-After' in trusted_response.headers.get('Access-Control-Expose-Headers', '')

    def test_startup_check_refuses_when_secret_key_insecure(self):
        """With DEBUG=False, refuses to boot if SECRET_KEY is missing, default, or short."""
        with override_settings(
            DEBUG=False,
            SECRET_KEY='django-insecure-production-ready-key-change-this',
            ALLOWED_HOSTS=['api.altsan.com'],
            CORS_ALLOWED_ORIGINS=['https://altsan.com']
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "SECRET_KEY is missing, using a known insecure default, or too short" in str(exc_info.value)

        # Short key (< 32 chars)
        with override_settings(
            DEBUG=False,
            SECRET_KEY='tooshortkey12345',
            ALLOWED_HOSTS=['api.altsan.com'],
            CORS_ALLOWED_ORIGINS=['https://altsan.com']
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "minimum 32 characters required" in str(exc_info.value)

    def test_startup_check_refuses_when_allowed_hosts_empty(self):
        """With DEBUG=False, refuses to boot if ALLOWED_HOSTS is empty or wildcard [*]."""
        with override_settings(
            DEBUG=False,
            SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
            ALLOWED_HOSTS=[],
            CORS_ALLOWED_ORIGINS=['https://altsan.com']
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "ALLOWED_HOSTS cannot be empty or wildcard [*]" in str(exc_info.value)

        with override_settings(
            DEBUG=False,
            SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
            ALLOWED_HOSTS=['*'],
            CORS_ALLOWED_ORIGINS=['https://altsan.com']
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "ALLOWED_HOSTS cannot be empty or wildcard [*]" in str(exc_info.value)

    def test_startup_check_refuses_when_cors_origins_empty(self):
        """With DEBUG=False, refuses to boot if CORS_ALLOWED_ORIGINS is empty."""
        with override_settings(
            DEBUG=False,
            SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
            ALLOWED_HOSTS=['api.altsan.com'],
            CORS_ALLOWED_ORIGINS=[]
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "CORS_ALLOWED_ORIGINS cannot be empty" in str(exc_info.value)

    def test_startup_check_passes_with_valid_production_settings(self):
        """With DEBUG=False and proper production secrets configured, startup check passes cleanly."""
        from unittest import mock
        with mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://postgres:1234@localhost:5432/altus'}):
            with override_settings(
                DEBUG=False,
                SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
                ALLOWED_HOSTS=['api.altsan.com', 'altsan.com'],
                CORS_ALLOWED_ORIGINS=['https://altsan.com', 'https://app.altsan.com'],
                PRIVATE_STORAGE_BUCKET='altsan-private-storage-bucket',
                SMS_PROVIDER='TWILIO',
                TWILIO_ACCOUNT_SID='AC1234567890abcdef1234567890abcdef',
                TWILIO_AUTH_TOKEN='authtoken1234567890abcdef123456',
                TWILIO_PHONE_NUMBER='+15551234567',
                OTP_HMAC_SECRET='dedicated-otp-hmac-secret-at-least-16-chars',
                REDIS_URL='redis://localhost:6379/0',
                DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'prod_db'}}
            ):
                # Should not raise any exception
                validate_production_settings()

    def test_startup_check_refuses_when_private_storage_missing(self):
        """With DEBUG=False, refuses to boot if PRIVATE_STORAGE_BUCKET is missing."""
        with override_settings(
            DEBUG=False,
            SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
            ALLOWED_HOSTS=['api.altsan.com'],
            CORS_ALLOWED_ORIGINS=['https://altsan.com'],
            PRIVATE_STORAGE_BUCKET='',
            SMS_PROVIDER='TWILIO'
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "Private object storage settings" in str(exc_info.value)

    def test_startup_check_refuses_when_sms_provider_missing(self):
        """With DEBUG=False, refuses to boot if SMS_PROVIDER is missing or on console backend."""
        with override_settings(
            DEBUG=False,
            SECRET_KEY='very-secure-production-key-at-least-32-characters-long!!',
            ALLOWED_HOSTS=['api.altsan.com'],
            CORS_ALLOWED_ORIGINS=['https://altsan.com'],
            PRIVATE_STORAGE_BUCKET='altsan-private-storage-bucket',
            SMS_PROVIDER='',
            SMS_BACKEND='core.sms.ConsoleSMSBackend'
        ):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                validate_production_settings()
            assert "No SMS provider configured" in str(exc_info.value)

    def test_check_default_passwords_fails_when_user_has_password123_or_altus123(self, db):
        """check_default_passwords command must fail and exit non-zero (raise CommandError) if password123 or altus123 is found."""
        User.objects.create_user(
            username='vuln_user_1',
            password='password123',
            email='vuln1@test.com'
        )
        with pytest.raises(CommandError) as exc_info1:
            call_command('check_default_passwords')
        assert "vuln_user_1" in str(exc_info1.value)
        assert "password123" in str(exc_info1.value)

        User.objects.create_user(
            username='vuln_user_2',
            password='altus123',
            email='vuln2@test.com'
        )
        with pytest.raises(CommandError) as exc_info2:
            call_command('check_default_passwords')
        assert "vuln_user_2" in str(exc_info2.value)
        assert "altus123" in str(exc_info2.value)

    def test_check_default_passwords_configurable_list(self, db):
        """check_default_passwords supports custom configurable banned password list via CLI and settings."""
        User.objects.create_user(
            username='custom_vuln_user',
            password='customsecret123',
            email='custom@test.com'
        )
        # Passes with default banned list
        call_command('check_default_passwords')

        # Fails when custom password is added to banned list via CLI
        with pytest.raises(CommandError) as exc_info:
            call_command('check_default_passwords', banned_passwords='customsecret123,badpass')
        assert "custom_vuln_user" in str(exc_info.value)
        assert "customsecret123" in str(exc_info.value)

        # Fails when custom password is configured in settings
        with override_settings(BANNED_DEFAULT_PASSWORDS=['customsecret123']):
            with pytest.raises(CommandError) as exc_info_sett:
                call_command('check_default_passwords')
            assert "custom_vuln_user" in str(exc_info_sett.value)

    def test_check_default_passwords_succeeds_when_all_passwords_secure(self, db):
        """check_default_passwords command passes cleanly when all users have secure passwords."""
        User.objects.create_user(
            username='safe_user_1',
            password='SuperSecurePassword987!',
            email='safe1@test.com'
        )
        User.objects.create_user(
            username='safe_user_2',
            password='AnotherSecurePassword654!',
            email='safe2@test.com'
        )
        # Should not raise
        call_command('check_default_passwords')
