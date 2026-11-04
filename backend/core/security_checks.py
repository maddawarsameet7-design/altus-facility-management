"""
core/security_checks.py — Validates critical production security settings on startup.
"""
import os
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

INSECURE_SECRET_KEYS = (
    'django-insecure-production-ready-key-change-this',
    'django-insecure-replace-with-secure-key-in-production',
    'django-insecure-',
    'secret',
    'changeme',
)


def validate_production_settings():
    """
    Ensures production deployment does not boot with dangerous defaults.
    Raises ImproperlyConfigured if any security condition is violated:
    - SECRET_KEY missing, using insecure default, or too short (< 32 chars).
    - ALLOWED_HOSTS empty or wildcard [*].
    - CORS_ALLOWED_ORIGINS empty.
    """
    if getattr(settings, 'DEBUG', False):
        return

    secret_key = getattr(settings, 'SECRET_KEY', '') or ''
    if not secret_key or len(secret_key) < 32 or any(secret_key.startswith(k) for k in INSECURE_SECRET_KEYS):
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! SECRET_KEY is missing, "
            "using a known insecure default, or too short (minimum 32 characters required when DEBUG=False)."
        )

    allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', []) or []
    if not allowed_hosts or allowed_hosts == ['*'] or allowed_hosts == ['']:
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! ALLOWED_HOSTS cannot be empty "
            "or wildcard [*] when DEBUG=False."
        )

    cors_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', []) or []
    if not cors_origins:
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! CORS_ALLOWED_ORIGINS cannot be empty when DEBUG=False."
        )

    private_storage = getattr(settings, 'PRIVATE_STORAGE_BUCKET', None)
    if not private_storage:
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! Private object storage settings "
            "(PRIVATE_STORAGE_BUCKET or AWS_STORAGE_BUCKET_NAME) must be configured when DEBUG=False."
        )

    sms_backend = getattr(settings, 'SMS_BACKEND', '') or ''
    sms_provider = (getattr(settings, 'SMS_PROVIDER', '') or os.environ.get('SMS_PROVIDER', '')).upper()
    if not sms_provider and (not sms_backend or 'console' in sms_backend.lower()):
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! No SMS provider configured. "
            "Set SMS_PROVIDER (e.g. 'TWILIO', 'AWS_SNS') or a production SMS_BACKEND when DEBUG=False."
        )

    # DATABASE_URL check: missing or not PostgreSQL
    db_url = os.environ.get('DATABASE_URL') or getattr(settings, 'DATABASE_URL', None)
    db_engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    if not db_url or 'postgresql' not in db_engine.lower():
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! DATABASE_URL is missing or "
            "database engine is not PostgreSQL when DEBUG=False."
        )

    # OTP_HMAC_SECRET check: missing or fallback to SECRET_KEY
    otp_hmac_secret = getattr(settings, 'OTP_HMAC_SECRET', None) or os.environ.get('OTP_HMAC_SECRET', None)
    if not otp_hmac_secret or otp_hmac_secret == getattr(settings, 'SECRET_KEY', None) or len(otp_hmac_secret) < 16:
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! OTP_HMAC_SECRET is missing or using SECRET_KEY. "
            "Dedicated secret key required when DEBUG=False."
        )

    # REDIS_URL check: missing
    redis_url = getattr(settings, 'REDIS_URL', None) or os.environ.get('REDIS_URL', None)
    if not redis_url:
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! REDIS_URL is missing when DEBUG=False."
        )

    # SMS provider credentials check
    if sms_provider == 'TWILIO':
        twilio_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None) or os.environ.get('TWILIO_ACCOUNT_SID', None)
        twilio_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None) or os.environ.get('TWILIO_AUTH_TOKEN', None)
        twilio_phone = getattr(settings, 'TWILIO_PHONE_NUMBER', None) or os.environ.get('TWILIO_PHONE_NUMBER', None)
        if not (twilio_sid and twilio_token and twilio_phone):
            raise ImproperlyConfigured(
                "SECURITY CRITICAL: Production startup aborted! SMS provider credentials missing: "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER must be configured when DEBUG=False."
            )
    elif sms_provider in ('AWS_SNS', 'SNS'):
        aws_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None) or os.environ.get('AWS_ACCESS_KEY_ID', None)
        aws_secret = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) or os.environ.get('AWS_SECRET_ACCESS_KEY', None)
        if not (aws_key and aws_secret):
            raise ImproperlyConfigured(
                "SECURITY CRITICAL: Production startup aborted! SMS provider credentials missing: "
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be configured when DEBUG=False."
            )

