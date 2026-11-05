import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .providers import SMSError, normalize_ng
from .tasks import send_sms_task

PURPOSES = ("signup", "login", "reset", "phone_change")


class OTPError(Exception):
    pass


def _phone_key(phone):
    return hashlib.sha256(phone.encode()).hexdigest()


def _otp_key(phone, purpose):
    return f"sms:otp:{purpose}:{_phone_key(phone)}"


def _cooldown_key(phone, purpose):
    return f"sms:cooldown:{purpose}:{_phone_key(phone)}"


def _code_hash(phone, purpose, code):
    value = f"{purpose}:{phone}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).hexdigest()


def send_otp(phone, purpose, ip):
    if purpose not in PURPOSES:
        raise SMSError("Invalid OTP purpose")
    phone = normalize_ng(phone)
    if not cache.add(_cooldown_key(phone, purpose), 1, timeout=settings.OTP_RESEND_SECONDS):
        raise SMSError("Please wait before requesting another code")
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = timezone.now().timestamp() + settings.OTP_TTL_SECONDS
    cache.set(_otp_key(phone, purpose), {
        "hash": _code_hash(phone, purpose, code), "attempts": 0, "expires_at": expires_at,
    }, timeout=settings.OTP_TTL_SECONDS)
    reference = f"otp-{purpose}-{uuid.uuid4().hex}"
    message = f"Your Netacess code is {code}. It expires in 5 minutes. Do not share it."
    result = send_sms_task.delay(phone, message, "otp", reference)
    outcome = result.result if result.ready() else None
    if isinstance(outcome, dict) and outcome.get("status") == "failed":
        return code, False, outcome.get("error", "SMS delivery failed")
    return code, True, ""


def verify_otp(phone, purpose, code):
    try:
        phone = normalize_ng(phone)
    except SMSError:
        raise OTPError() from None
    if purpose not in PURPOSES:
        raise OTPError()
    key = _otp_key(phone, purpose)
    record = cache.get(key)
    now = timezone.now().timestamp()
    if not record or record["expires_at"] <= now or record["attempts"] >= settings.OTP_MAX_ATTEMPTS:
        cache.delete(key)
        raise OTPError()
    actual = _code_hash(phone, purpose, str(code))
    if not secrets.compare_digest(record["hash"], actual):
        record["attempts"] += 1
        remaining = max(1, int(record["expires_at"] - now))
        cache.set(key, record, timeout=remaining)
        raise OTPError()
    cache.delete(key)
    return phone