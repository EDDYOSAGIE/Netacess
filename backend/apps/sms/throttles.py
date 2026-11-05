import hashlib

from django.core.cache import cache
from rest_framework.throttling import BaseThrottle

from .providers import SMSError, normalize_ng


class OTPPhoneIPThrottle(BaseThrottle):
    limits = ((60, 3), (3600, 10))

    def allow_request(self, request, view):
        try:
            phone = normalize_ng(request.data.get("phone", ""))
        except (SMSError, AttributeError):
            phone = "invalid"
        phone_hash = hashlib.sha256(phone.encode()).hexdigest()
        ip = request.META.get("REMOTE_ADDR", "unknown")
        keys = []
        for identity in (f"phone:{phone_hash}", f"ip:{ip}"):
            for period, limit in self.limits:
                key = f"sms:throttle:{identity}:{period}"
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
        return True

    def wait(self):
        return getattr(self, "wait_seconds", None)