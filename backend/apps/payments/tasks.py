import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Payment
from .providers.base import ProviderError
from .services import check_payment, expire_stale

log = logging.getLogger(__name__)


@shared_task(name="payments.poll", bind=True, max_retries=5)
def poll_payment(self, payment_id):
    try:
        return check_payment(payment_id, "poll").status
    except ProviderError as e:
        if self.app.conf.task_always_eager:
            log.warning("poll failed: %s", e)
            return "ERROR"
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries * 10, 300))


@shared_task(name="payments.reconcile_pending")
def reconcile_pending():
    """Every 15 minutes: re-check anything unresolved so no paid order is left behind."""
    cutoff = timezone.now() - timedelta(days=2)
    open_states = [Payment.INITIATED, Payment.PENDING, Payment.FAILED, Payment.EXPIRED]
    checked = 0
    for p in Payment.objects.filter(status__in=open_states, created_at__gte=cutoff).exclude(
            provider_reference__startswith="pending-"):
        try:
            check_payment(p.id, "poll")
            checked += 1
        except ProviderError as e:
            log.warning("reconcile %s failed: %s", p.id, e)
        p.refresh_from_db()
        expire_stale(p)
    # Attempts that never got a provider reference and have timed out
    for p in Payment.objects.filter(status__in=[Payment.INITIATED, Payment.PENDING], expires_at__lt=timezone.now()):
        expire_stale(p)
    return checked
