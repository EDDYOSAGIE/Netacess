import uuid

from django.db import models


class Notification(models.Model):
    IN_APP, SMS, EMAIL = "in_app", "sms", "email"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30)  # payment_received, code_issued, plan_reminder, payment_failed
    title = models.CharField(max_length=120)
    body = models.TextField()
    channel = models.CharField(max_length=10, default=IN_APP)
    link = models.CharField(max_length=200, blank=True)  # where clicking it goes
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "dedupe_key"], condition=~models.Q(dedupe_key=""), name="uniq_notif_dedupe")]
        indexes = [models.Index(fields=["user", "-created_at"])]
