import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone


class EmailOTPError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def _key(email, purpose):
    digest = hashlib.sha256(email.encode()).hexdigest()
    return f"email:otp:{purpose}:{digest}"


def _cooldown_key(email, purpose):
    digest = hashlib.sha256(email.encode()).hexdigest()
    return f"email:otp:cooldown:{purpose}:{digest}"


def _code_hash(email, purpose, code):
    value = f"{purpose}:{email}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).hexdigest()


def send_email_otp(email, purpose):
    if not cache.add(_cooldown_key(email, purpose), 1, timeout=settings.OTP_RESEND_SECONDS):
        raise EmailOTPError("too_soon", "Wait a minute before asking for another code.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS)
    cache.set(_key(email, purpose), {
        "hash": _code_hash(email, purpose, code),
        "attempts": 0,
        "expires_at": expires_at.timestamp(),
    }, timeout=settings.OTP_TTL_SECONDS)
    try:
        send_mail(
            "Your Netacess verification code",
            f"Your Netacess verification code is {code}. It expires in 5 minutes. Do not share it.",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception:
        cache.delete(_key(email, purpose))
        cache.delete(_cooldown_key(email, purpose))
        raise EmailOTPError("email_unavailable", "Could not send an email code right now.") from None


def verify_email_otp(email, purpose, code):
    key = _key(email, purpose)
    record = cache.get(key)
    now = timezone.now().timestamp()
    if not record or record["expires_at"] <= now or record["attempts"] >= settings.OTP_MAX_ATTEMPTS:
        cache.delete(key)
        raise EmailOTPError("invalid_code", "The code is invalid or expired.")

    expected = _code_hash(email, purpose, str(code))
    if not hmac.compare_digest(record["hash"], expected):
        record["attempts"] += 1
        cache.set(key, record, timeout=max(1, int(record["expires_at"] - now)))
        raise EmailOTPError("invalid_code", "The code is invalid or expired.")

    cache.delete(key)