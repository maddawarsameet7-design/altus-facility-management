import hashlib
import hmac
import re
import secrets
from django.conf import settings


def normalize_phone(phone: str) -> str:
    """
    Normalizes phone input to standard E.164-compatible format where possible,
    removing spaces, dashes, parentheses.
    """
    if not phone:
        return ""
    cleaned = re.sub(r'[\s\-\(\)]', '', str(phone).strip())
    # If 10 digits without country code, prefix with +91 (India) or keep as-is if already with '+'
    if cleaned.isdigit() and len(cleaned) == 10:
        cleaned = f"+91{cleaned}"
    elif cleaned.isdigit() and len(cleaned) == 12 and cleaned.startswith('91'):
        cleaned = f"+{cleaned}"
    return cleaned


def generate_otp_code(digits: int = 6) -> str:
    """
    Generates a cryptographically secure random N-digit numeric OTP code.
    """
    lower = 10 ** (digits - 1)
    upper = (10 ** digits) - 1
    code_int = secrets.randbelow(upper - lower + 1) + lower
    return str(code_int)


def hash_otp_code(phone: str, code: str) -> str:
    """
    Computes an HMAC-SHA256 digest of phone + code using OTP_HMAC_SECRET or SECRET_KEY.
    Amendment 12: HMAC-SHA256 with a secret key from an env var.
    """
    secret = getattr(settings, 'OTP_HMAC_SECRET', None) or settings.SECRET_KEY
    normalized = normalize_phone(phone)
    msg = f"{normalized}:{code}".encode('utf-8')
    return hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def verify_otp_code(phone: str, code: str, expected_hash: str) -> bool:
    """
    Verifies the OTP code against expected HMAC digest using hmac.compare_digest
    to prevent timing attacks.
    Amendment 12: hmac.compare_digest.
    """
    computed = hash_otp_code(phone, code)
    return hmac.compare_digest(computed, expected_hash)
