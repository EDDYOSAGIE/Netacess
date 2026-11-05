import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.plans.models import Subscription

from .models import SMSLog
from .providers import assert_allowed, get_provider, redact_sensitive

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, name="sms.send")
def send_sms_task(self, to, message, purpose, reference):
    try:
        entry, _ = SMSLog.objects.get_or_create(
            reference=reference,
            defaults={"to": to, "purpose": purpose, "status": SMSLog.QUEUED},
        )
    except IntegrityError:
        entry = SMSLog.objects.get(reference=reference)
    if entry.status == SMSLog.SENT:
        return {"status": SMSLog.SENT, "message_id": entry.provider_message_id}

    try:
        provider = get_provider()
        if settings.SMS_PROVIDER != "console":
            assert_allowed(to)
        outbound_message = "[redacted sensitive SMS]" if purpose == "access_code" and settings.SMS_PROVIDER == "console" else message
        message_id = provider.send(to, outbound_message)
    except Exception as exc:
        error = redact_sensitive(exc, message)[:2000]
        entry.status = SMSLog.FAILED
        entry.error = error
        entry.save(update_fields=["status", "error"])
        if settings.USE_REDIS and self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        log.error("SMS send failed for reference %s: %s", reference, error)
        return {"status": SMSLog.FAILED, "error": error}

    entry.status = SMSLog.SENT
    entry.provider_message_id = str(message_id or "")[:128]
    entry.error = ""
    entry.save(update_fields=["status", "provider_message_id", "error"])
    return {"status": SMSLog.SENT, "message_id": entry.provider_message_id}


@shared_task(name="sms.send_expiry_reminders")
def send_expiry_reminders():
    if not settings.USE_REDIS:
        return 0
    now = timezone.now()
    subscriptions = Subscription.objects.filter(
        status=Subscription.ACTIVE,
        expires_at__gt=now + timedelta(days=2) - timedelta(hours=1),
        expires_at__lte=now + timedelta(days=2),
    ).select_related("user")
    queued = 0
    for subscription in subscriptions:
        reference = f"reminder-{subscription.id}-{subscription.expires_at.date()}"
        if SMSLog.objects.filter(reference=reference, status=SMSLog.SENT).exists():
            continue
        message = f"Your Netacess plan expires on {subscription.expires_at:%b %d, %Y}. Renew to stay connected."
        send_sms_task.delay(subscription.user.phone, message, "expiry_reminder", reference)
        queued += 1
    return queued