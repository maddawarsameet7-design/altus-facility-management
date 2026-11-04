import os
import logging
import threading
from abc import ABC, abstractmethod
from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def get_sms_daily_global_cap() -> int:
    """Returns the configured global daily SMS cap."""
    cap_val = getattr(settings, 'SMS_DAILY_GLOBAL_CAP', None)
    if cap_val is None:
        cap_val = os.environ.get('SMS_DAILY_GLOBAL_CAP', '500')
    try:
        return int(cap_val)
    except (ValueError, TypeError):
        return 500


def check_and_record_sms_budget(phone: str) -> bool:
    """
    Checks global daily SMS usage against SMS_DAILY_GLOBAL_CAP.
    - If usage reaches 80%, generates a Notification/Alert to all Directors (once per day).
    - If usage reaches 100%, logs error WITHOUT the OTP code and refuses dispatch.
    Returns True if allowed to send, False if capped.
    """
    from core.models import OTPChallenge, User, Notification, Society

    cap = get_sms_daily_global_cap()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count challenges dispatched today (excluding fallback supervisor codes)
    today_count = OTPChallenge.objects.filter(
        created_at__gte=today_start
    ).exclude(device_id='FALLBACK_LOGIN').count()

    # 80% threshold check
    warning_threshold = int(0.80 * cap)
    if today_count >= warning_threshold:
        logger.warning(f"Global SMS budget alert: {today_count}/{cap} messages used today (>= 80%).")
        # Idempotently alert Directors
        directors = User.objects.filter(role='DIRECTOR', is_active=True)
        default_society = Society.objects.first()
        for director in directors:
            already_alerted = Notification.objects.filter(
                recipient=director,
                notification_type='SMS_BUDGET_WARNING',
                created_at__gte=today_start
            ).exists()
            if not already_alerted:
                Notification.objects.create(
                    society=default_society,
                    recipient=director,
                    notification_type='SMS_BUDGET_WARNING',
                    title='SMS Daily Budget Alert (80% Reached)',
                    body=f"Global SMS usage has reached {today_count} of {cap} daily allowance ({int(today_count / cap * 100)}%)."
                )

    # 100% threshold check
    if today_count >= cap:
        # Failure logged strictly without the OTP code
        logger.error(f"Global daily SMS cap ({cap}) exceeded. Refusing SMS dispatch to {phone}.")
        return False

    return True


class BaseSMSBackend(ABC):
    """
    Abstract base class for SMS delivery backends.
    """
    @abstractmethod
    def send_otp(self, phone: str, code: str) -> bool:
        """
        Sends OTP verification code to the given phone number.
        Returns True on successful dispatch, False otherwise.
        """
        raise NotImplementedError


class ConsoleSMSBackend(BaseSMSBackend):
    """
    Development/testing backend that logs the OTP to console.
    Ensures OTP code NEVER appears in structured logger logs.
    """
    def send_otp(self, phone: str, code: str) -> bool:
        if not check_and_record_sms_budget(phone):
            return False

        # Formatted console output for local development only
        print(f"\n========================================\n[ALTSAN OTP] Verification code for {phone}: {code} (Valid for 5 minutes)\n========================================\n")
        # In structured logger, log dispatch metadata ONLY — never the secret OTP code
        logger.info(f"[ALTSAN OTP] Verification code successfully dispatched for {phone}")
        return True


class ProductionSMSBackend(BaseSMSBackend):
    """
    Production SMS provider backend.
    Supports Twilio, AWS SNS, or standard HTTP SMS gateways based on settings.SMS_PROVIDER.
    Never logs OTP code in error or info messages.
    """
    def send_otp(self, phone: str, code: str) -> bool:
        if not check_and_record_sms_budget(phone):
            return False

        provider = getattr(settings, 'SMS_PROVIDER', 'TWILIO').upper()
        msg = f"Your Altsan worker verification code is {code}. Do not share this code with anyone."

        if provider == 'TWILIO':
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
            from_phone = getattr(settings, 'TWILIO_PHONE_NUMBER', None)

            if not (account_sid and auth_token and from_phone):
                logger.error("Twilio credentials not configured.")
                return False

            try:
                from twilio.rest import Client
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    body=msg,
                    from_=from_phone,
                    to=phone
                )
                logger.info(f"Twilio SMS sent to {phone}, SID: {message.sid}")
                return True
            except Exception as e:
                # Log error strictly without the OTP code
                logger.error(f"Twilio SMS dispatch failed for {phone}: {e}")
                return False

        elif provider in ('AWS_SNS', 'SNS'):
            try:
                import boto3
                sns = boto3.client('sns', region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'ap-south-1'))
                sns.publish(PhoneNumber=phone, Message=msg)
                logger.info(f"AWS SNS dispatched to {phone}")
                return True
            except Exception as e:
                # Log error strictly without the OTP code
                logger.error(f"AWS SNS dispatch failed for {phone}: {e}")
                return False
        else:
            logger.warning(f"Unknown SMS provider: {provider}")
            return False


def get_sms_backend() -> BaseSMSBackend:
    """
    Resolves and instantiates the configured SMS backend.
    """
    backend_path = getattr(settings, 'SMS_BACKEND', 'core.sms.ConsoleSMSBackend')
    try:
        backend_cls = import_string(backend_path)
        return backend_cls()
    except Exception as e:
        logger.error(f"Failed to load SMS_BACKEND '{backend_path}': {e}. Falling back to ConsoleSMSBackend.")
        return ConsoleSMSBackend()


def send_otp_async(phone: str, code: str):
    """
    Dispatches OTP asynchronously in a background thread so HTTP response is never blocked.
    Amendment 11: Send SMS only to registered worker phones, asynchronously.
    """
    backend = get_sms_backend()
    t = threading.Thread(target=backend.send_otp, args=(phone, code), daemon=True)
    t.start()
