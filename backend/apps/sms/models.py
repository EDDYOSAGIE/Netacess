from django.db import models


class SMSLog(models.Model):
    QUEUED, SENT, FAILED = "queued", "sent", "failed"
    STATUSES = [(QUEUED, "Queued"), (SENT, "Sent"), (FAILED, "Failed")]

    to = models.CharField(max_length=20)
    purpose = models.CharField(max_length=32)
    reference = models.CharField(max_length=180, unique=True)
    provider_message_id = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=8, choices=STATUSES, default=QUEUED)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.purpose} SMS to {self.to}: {self.status}"