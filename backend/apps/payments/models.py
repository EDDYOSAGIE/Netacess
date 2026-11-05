import uuid

from django.db import models


class Payment(models.Model):
    INITIATED, PENDING, SUCCESSFUL = "INITIATED", "PENDING", "SUCCESSFUL"
    FAILED, EXPIRED, NEEDS_REVIEW, REFUNDED = "FAILED", "EXPIRED", "NEEDS_REVIEW", "REFUNDED"
    STATUSES = [(s, s.title()) for s in
                (INITIATED, PENDING, SUCCESSFUL, FAILED, EXPIRED, NEEDS_REVIEW, REFUNDED)]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=16)
    provider_reference = models.CharField(max_length=128)  # tx_ref (Flutterwave) or payment_ref (Espees)
    amount = models.DecimalField(max_digits=18, decimal_places=4)  # NGN kobo or ESP
    currency = models.CharField(max_length=4)  # "NGN" (kobo) or "ESP"
    status = models.CharField(max_length=14, choices=STATUSES, default=INITIATED)
    checkout_url = models.URLField(max_length=500, blank=True)
    card_brand = models.CharField(max_length=32, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "provider_reference"], name="uniq_provider_ref")]
        indexes = [models.Index(fields=["status", "created_at"])]


class PaymentEvent(models.Model):
    """Append-only log of everything we hear about a payment."""
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="events")
    source = models.CharField(max_length=12)  # webhook, poll, admin, system
    event_type = models.CharField(max_length=40)
    event_id = models.CharField(max_length=128, blank=True)  # provider's id, for webhook de-duplication
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["payment", "source", "event_id"], condition=~models.Q(event_id=""),
            name="uniq_payment_event")]
        indexes = [models.Index(fields=["payment", "received_at"])]
