import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
app = Celery("netacess")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "reconcile-pending-payments": {"task": "payments.reconcile_pending", "schedule": 900.0},
    "remind-stale-reviews": {"task": "adminops.remind_stale_reviews", "schedule": 1800.0},
    "expiry-reminders": {"task": "notifications.send_expiry_reminders", "schedule": 3600.0},
}
if settings.USE_REDIS:
    app.conf.beat_schedule["sms-expiry-reminders"] = {
        "task": "sms.send_expiry_reminders", "schedule": 3600.0,
    }
