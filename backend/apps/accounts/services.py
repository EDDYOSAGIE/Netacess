import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuthToken, PhoneOTP, User
from .sms import send_sms


class OTPError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def normalize_phone(raw):
    p = re.sub(r"[\s\-()]", "", raw or "")
    if p.startswith("0") and len(p) == 11:
        p = "+234" + p[1:]
    elif p.startswith("234"):
        p = "+" + p
    if not re.fullmatch(r"\+\d{10,15}", p):
        raise OTPError("invalid_phone", "Enter a valid phone number")
    return p


def _hash(phone, code):
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def request_otp(phone, ip=None):
    now = timezone.now()
    recent = PhoneOTP.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1))
    if recent.count() >= settings.OTP_MAX_PER_HOUR:
        raise OTPError("rate_limited", "Too many codes requested. Try again later.")
    last = recent.order_by("-created_at").first()
    if last and (now - last.created_at).total_seconds() < settings.OTP_RESEND_SECONDS:
        raise OTPError("too_soon", "Wait a minute before asking for another code.")
    code = f"{secrets.randbelow(10**6):06d}"
    PhoneOTP.objects.create(
        phone=phone, code_hash=_hash(phone, code), ip=ip,
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS))
    send_sms(phone, f"Your Netacess code is {code}. It is valid for 5 minutes.")


def verify_otp(phone, code, full_name="", email="", password=None):
    # Errors are returned from inside the transaction and raised after it commits,
    # otherwise a wrong guess would roll back its own attempt counter.
    with transaction.atomic():
        user, err = _check_otp(phone, code, full_name, email, password)
    if err:
        raise err
    return user, AuthToken.issue(user)


def _check_otp(phone, code, full_name, email, password):
    now = timezone.now()
    otp = (PhoneOTP.objects.select_for_update()
           .filter(phone=phone, consumed_at__isnull=True).order_by("-created_at").first())
    if not otp:
        return None, OTPError("no_code", "Request a new code.")
    if otp.expires_at < now:
        return None, OTPError("expired", "This code has expired.")
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        return None, OTPError("too_many_attempts", "Too many attempts. Request a new code.")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _hash(phone, code)):
        otp.save(update_fields=["attempts"])
        return None, OTPError("wrong_code", "That code is not right.")
    otp.consumed_at = now
    otp.save(update_fields=["attempts", "consumed_at"])
    user, created = User.objects.get_or_create(phone=phone, defaults={"full_name": full_name, "email": email})
    if created and password:
        user.set_password(password)
    user.is_phone_verified = True
    user.save()
    return user, None
