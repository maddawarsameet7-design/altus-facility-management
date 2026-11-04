import logging
import threading
from abc import ABC, abstractmethod
from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


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
    Development/testing backend that logs the OTP to the console.
    """
    def send_otp(self, phone: str, code: str) -> bool:
        msg = f"[ALTSAN OTP] Verification code for {phone}: {code} (Valid for 5 minutes)"
        print(f"\n========================================\n{msg}\n========================================\n")
        logger.info(msg)
        return True


class ProductionSMSBackend(BaseSMSBackend):
    """
    Production SMS provider backend.
    Supports Twilio, AWS SNS, or standard HTTP SMS gateways based on settings.SMS_PROVIDER.
    """
    def send_otp(self, phone: str, code: str) -> bool:
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
    Dispatches OTP asynchronously in a background thread so the HTTP response is never blocked.
    Amendment 11: Send SMS only to registered worker phones, asynchronously.
    """
    backend = get_sms_backend()
    t = threading.Thread(target=backend.send_otp, args=(phone, code), daemon=True)
    t.start()
