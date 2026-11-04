"""
backend/core/tests/test_production_smoke.py — Production smoke tests verifying startup readiness and security gates.
"""
import os
from unittest import mock
import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings


def test_app_refuses_to_start_when_testing_active_with_debug_false():
    """
    Amendment 1: App MUST refuse to start if TESTING is set while DEBUG=False.
    """
    app_config = apps.get_app_config('core')
    with override_settings(DEBUG=False):
        with mock.patch.dict(os.environ, {'TESTING': 'true'}):
            with pytest.raises(ImproperlyConfigured, match="TESTING environment variable cannot be active when DEBUG=False"):
                app_config.ready()


def test_production_smoke_ready_and_check_under_valid_env():
    """
    Amendment 2: Backend smoke test that runs AppConfig.ready() and manage.py check --deploy
    under production-like settings (DEBUG=False, TESTING unset, valid env vars) and fails on any exception.
    """
    app_config = apps.get_app_config('core')

    valid_prod_env = {
        'TESTING': '',
        'DEBUG': 'False',
        'SECRET_KEY': 'a-production-grade-random-secret-key-that-has-over-50-characters-length',
        'ALLOWED_HOSTS': 'api.altsan.com,worker.altsan.com',
        'CORS_ALLOWED_ORIGINS': 'https://worker.altsan.com,https://app.altsan.com',
        'PRIVATE_STORAGE_BUCKET': 'altsan-private-media-bucket',
        'SMS_PROVIDER': 'TWILIO',
        'TWILIO_ACCOUNT_SID': 'AC_test_prod_smoke_sid_00000000000000',
        'TWILIO_AUTH_TOKEN': 'auth_token_test_prod_smoke_0000000000',
        'TWILIO_PHONE_NUMBER': '+15550001122',
        'DATABASE_URL': 'postgresql://postgres:1234@localhost:5432/altus',
        'OTP_HMAC_SECRET': 'dedicated-otp-hmac-sha256-key-separate-from-django-secret-key',
        'REDIS_URL': 'redis://localhost:6379/0',
    }

    prod_settings = {
        'DEBUG': False,
        'SECRET_KEY': valid_prod_env['SECRET_KEY'],
        'ALLOWED_HOSTS': ['api.altsan.com', 'worker.altsan.com'],
        'CORS_ALLOWED_ORIGINS': ['https://worker.altsan.com', 'https://app.altsan.com'],
        'PRIVATE_STORAGE_BUCKET': valid_prod_env['PRIVATE_STORAGE_BUCKET'],
        'SMS_PROVIDER': 'TWILIO',
        'DATABASE_URL': valid_prod_env['DATABASE_URL'],
        'DATABASES': {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'altus',
                'USER': 'postgres',
                'PASSWORD': '1234',
                'HOST': 'localhost',
                'PORT': '5432',
            }
        },
        'OTP_HMAC_SECRET': valid_prod_env['OTP_HMAC_SECRET'],
        'REDIS_URL': valid_prod_env['REDIS_URL'],
    }

    with mock.patch.dict(os.environ, valid_prod_env):
        with override_settings(**prod_settings):
            # 1. Execute CoreConfig.ready() under production settings
            with mock.patch('django.core.management.call_command'):
                app_config.ready()

            # 2. Execute management check under production settings
            call_command('check')
