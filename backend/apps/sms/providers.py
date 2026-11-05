import logging
import re

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class SMSError(Exception):
    pass


def normalize_ng(number):
    value = re.sub(r"[\s\-+()]", "", str(number or ""))
    if value.startswith("0"):
        value = "234" + value[1:]
    if not re.fullmatch(r"234\d{10}", value):
        raise SMSError("Enter a valid Nigerian phone number")
    return value


def assert_allowed(number):
    normalized = normalize_ng(number)
    allowlist = [normalize_ng(item) for item in settings.SMS_ALLOWLIST]
    if allowlist and normalized not in allowlist:
        raise SMSError("This number is not on the SMS allowlist")
    return normalized


def redact_sensitive(value, message=""):
    value = str(value)
    if settings.TERMII_API_KEY:
        value = value.replace(settings.TERMII_API_KEY, "[redacted]")
    if message:
        value = value.replace(message, "[redacted message]")
    return re.sub(r"NETACESS_[A-Z0-9_]+|(?<!\d)\d{6}(?!\d)", "[redacted]", value)


class TermiiProvider:
    def send(self, to, message):
        normalized = assert_allowed(to)
        if not settings.TERMII_API_KEY:
            raise SMSError("TERMII_API_KEY is not configured")
        try:
            response = requests.post(
                f"{settings.TERMII_BASE_URL}/api/sms/send",
                json={
                    "to": normalized,
                    "from": settings.TERMII_SENDER_ID,
                    "sms": message,
                    "type": "plain",
                    "channel": settings.TERMII_CHANNEL,
                    "api_key": settings.TERMII_API_KEY,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            raise SMSError(redact_sensitive(exc, message)) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("message") or payload.get("error") or response.text or "Termii request failed"
        error = redact_sensitive(error, message)
        code = str(payload.get("code", "")).lower()
        message_id = payload.get("message_id") or payload.get("messageId")
        if response.status_code != 200 or payload.get("error") or code not in ("", "ok", "200") or not message_id:
            log.error("Termii SMS send failed: %s", error)
            raise SMSError(error)
        return str(message_id)


class ConsoleProvider:
    def send(self, to, message):
        safe_message = re.sub(r"NETACESS_[A-Z0-9_]+", "[redacted]", message)
        print(f"[SMS to {to}] {safe_message}")
        return "console-fake-id"


def get_provider():
    if settings.SMS_PROVIDER == "termii":
        return TermiiProvider()
    if settings.SMS_PROVIDER == "console":
        if not settings.DEBUG and not settings.DEMO_MODE:
            raise SMSError("The console SMS provider is available only in DEBUG mode")
        return ConsoleProvider()
    raise SMSError(f"Unsupported SMS provider: {settings.SMS_PROVIDER}")