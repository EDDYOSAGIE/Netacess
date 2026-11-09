import hashlib
import logging

from django.core.cache import cache
from rest_framework.exceptions import APIException
from rest_framework.throttling import BaseThrottle

log = logging.getLogger(__name__)


class CacheUnavailable(APIException):
    status_code = 503
    default_detail = "Authentication service is temporarily unavailable. Please try again shortly."
    default_code = "cache_unavailable"


class OTPEmailIPThrottle(BaseThrottle):
    limits = ((60, 3), (3600, 10))

    def allow_request(self, request, view):
        email = str(request.data.get("email", "")).strip().lower()
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        ip = request.META.get("REMOTE_ADDR", "unknown")
        keys = []
        try:
            for identity in (f"email:{email_hash}", f"ip:{ip}"):
                for period, limit in self.limits:
                    key = f"auth:throttle:{identity}:{period}"
                    current = cache.get(key, 0)
                    if current >= limit:
                        self.wait_seconds = period
                        return False
                    keys.append((key, period))
            for key, period in keys:
                if cache.add(key, 1, timeout=period):
                    continue
                try:
                    cache.incr(key)
                except ValueError:
                    cache.add(key, 1, timeout=period)
        except Exception as exc:
            log.error("OTP throttle cache unavailable (%s)", type(exc).__name__)
            raise CacheUnavailable() from None
        return True

    def wait(self):
        return getattr(self, "wait_seconds", None)