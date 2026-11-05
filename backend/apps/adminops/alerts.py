"""Alerts to staff. Three channels, and a failure in any of them never affects a payment."""
import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User
from apps.accounts.sms import send_sms
from apps.notifications.services import notify

log = logging.getLogger(__name__)


def alert_staff(title, body, path="", dedupe=""):
    staff = list(User.objects.filter(is_staff=True, is_active=True))
    link = path
    # 1. In-app (the bell in the admin screen). Always works, even if email and SMS are down.
    for u in staff:
        try:
            notify(u, "admin_alert", title, body, dedupe_key=f"{dedupe}:{u.id}" if dedupe else "", link=link)
        except Exception:
            log.exception("in-app alert failed")
    # 2. Email
    emails = sorted({u.email for u in staff if u.email} | set(settings.ADMIN_ALERT_EMAILS))
    if emails:
        url = f"{settings.FRONTEND_URL}{path}" if path else settings.FRONTEND_URL + "/admin"
        try:
            send_mail(f"[Netacess] {title}", f"{body}\n\nOpen it: {url}\n", settings.DEFAULT_FROM_EMAIL, emails,
                      fail_silently=False)
        except Exception:
            log.exception("alert email failed")
    # 3. SMS (short)
    if settings.ADMIN_ALERT_SMS:
        for u in staff:
            try:
                send_sms(u.phone, f"Netacess alert: {title}. Open the admin screen.")
            except Exception:
                log.exception("alert sms failed")
