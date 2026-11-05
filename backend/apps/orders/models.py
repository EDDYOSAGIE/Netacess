import uuid

from django.db import models


class Order(models.Model):
    PENDING, PAID, FAILED, EXPIRED = "PENDING", "PAID", "FAILED", "EXPIRED"
    STATUSES = [(PENDING, "Pending"), (PAID, "Paid"), (FAILED, "Failed"), (EXPIRED, "Expired")]
    FLUTTERWAVE, ESPEES = "flutterwave", "espees"
    PROVIDERS = [(FLUTTERWAVE, "Flutterwave"), (ESPEES, "Espees")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="orders")
    plan = models.ForeignKey("plans.Plan", on_delete=models.PROTECT)
    provider = models.CharField(max_length=16, choices=PROVIDERS)
    amount_ngn_kobo = models.PositiveBigIntegerField(null=True, blank=True)  # Flutterwave orders
    amount_esp = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)  # Espees orders
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    idempotency_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "idempotency_key"], name="uniq_order_idem")]
        indexes = [models.Index(fields=["user", "-created_at"])]
