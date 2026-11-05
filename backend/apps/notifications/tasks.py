from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.plans.models import Subscription

from .services import notify


@shared_task(name="notifications.send_expiry_reminders")
def send_expiry_reminders():
    """3 days and 1 day before a plan ends. Safe to run repeatedly."""
    now = timezone.now()
    sent = 0
    for days in (3, 1):
        window_end = now + timedelta(days=days)
        subs = Subscription.objects.filter(
            status=Subscription.ACTIVE, expires_at__gt=now, expires_at__lte=window_end
        ).select_related("user")
        for s in subs:
            made = notify(
                s.user, "plan_reminder", "Plan reminder",
                f"Your plan ends on {s.expires_at:%b %d, %Y}. Renew to stay connected.",
                dedupe_key=f"reminder:{s.id}:{days}d")
            sent += 1 if made else 0
    return sent
