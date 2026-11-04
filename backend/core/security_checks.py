"""
core/security_checks.py — Validates critical production security settings on startup.
"""
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
    sms_provider = getattr(settings, 'SMS_PROVIDER', '') or ''
    if not sms_provider and (not sms_backend or 'console' in sms_backend.lower()):
        raise ImproperlyConfigured(
            "SECURITY CRITICAL: Production startup aborted! No SMS provider configured. "
            "Set SMS_PROVIDER (e.g. 'TWILIO', 'AWS_SNS') or a production SMS_BACKEND when DEBUG=False."
        )

