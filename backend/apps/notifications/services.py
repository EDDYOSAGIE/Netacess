from django.db import IntegrityError, transaction

from .models import Notification


def notify(user, kind, title, body, dedupe_key="", link=""):
    """In-app notification. A dedupe_key makes repeated calls harmless."""
    try:
        with transaction.atomic():
            return Notification.objects.create(user=user, kind=kind, title=title, body=body,
                                               dedupe_key=dedupe_key, link=link)
    except IntegrityError:
        return None
