import base64
import hashlib
import secrets

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

from .models import AccessCode


def _fernet():
    key = settings.ACCESS_CODE_ENC_KEY
    if not key:
        if not settings.DEBUG:
            raise RuntimeError("ACCESS_CODE_ENC_KEY must be set in production")
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()).decode()
    return Fernet(key)


def code_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


def generate_code(plan_code):
    """NETACESS_<PLAN>_<16 random digits>"""
    digits = "".join(secrets.choice("0123456789") for _ in range(16))
    return f"NETACESS_{plan_code}_{digits}"


def decrypt(access_code):
    return _fernet().decrypt(access_code.code_encrypted.encode()).decode()


def issue_code(payment, subscription):
    """Creates exactly one code per payment (OneToOne), so retries are harmless."""
    existing = AccessCode.objects.filter(payment=payment).first()
    if existing:
        return existing
    plan_code = subscription.plan.code
    for _ in range(5):  # collisions are astronomically unlikely, but the DB constraint decides
        code = generate_code(plan_code)
        if not AccessCode.objects.filter(code_hash=code_hash(code)).exists():
            return AccessCode.objects.create(
                subscription=subscription, payment=payment, plan_code=plan_code,
                code_hash=code_hash(code), code_encrypted=_fernet().encrypt(code.encode()).decode())
    raise RuntimeError("Could not generate a unique access code")


def validate_code(code):
    """Returns the AccessCode if the code is genuine, active and its plan has not expired, else None.
    Ready for the fiber platform (or any other system) to call once that connection exists."""
    ac = (AccessCode.objects.select_related("subscription")
          .filter(code_hash=code_hash((code or "").strip().upper())).first())
    if not ac or ac.status != AccessCode.ACTIVE:
        return None
    sub = ac.subscription
    if sub.status != "ACTIVE" or sub.expires_at <= timezone.now():
        return None
    return ac
