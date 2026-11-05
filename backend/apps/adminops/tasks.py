from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.payments.models import Payment

from .alerts import alert_staff


@shared_task(name="adminops.send_alert")
def send_alert(title, body, path="", dedupe=""):
    alert_staff(title, body, path, dedupe)


@shared_task(name="adminops.remind_stale_reviews")
def remind_stale_reviews():
    """A payment left in review for over an hour gets a reminder, then again every 6 hours."""
    cutoff = timezone.now() - timedelta(minutes=settings.ADMIN_REVIEW_REMINDER_MINUTES)
    stale = Payment.objects.filter(status=Payment.NEEDS_REVIEW, updated_at__lt=cutoff)
    n = stale.count()
    if n and cache.add("review_reminder", 1, 6 * 3600):
        alert_staff(f"{n} payment{'s' if n != 1 else ''} still waiting for review",
                    "Money has been received that needs a decision. The customer is waiting.", "/admin")
        return n
    return 0
