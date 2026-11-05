from django.db import models


class ProviderSetting(models.Model):
    """Turn a payment provider on or off without a deploy."""
    provider = models.CharField(max_length=16, unique=True)
    is_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class CurrencyRate(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    esp_to_ngn = models.DecimalField(max_digits=16, decimal_places=4, default=4000)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        rate, _ = cls.objects.get_or_create(pk=1, defaults={"esp_to_ngn": 4000})
        return rate


class AuditLog(models.Model):
    """Every staff action: who, what, which record, and why."""
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="audit_entries")
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=64)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["-created_at"])]
