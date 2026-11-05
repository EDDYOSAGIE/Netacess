import uuid

from django.db import models


class Plan(models.Model):
    ONETIME = "ONETIME"
    MONTHLY = "MONTHLY"
    CODES = [(ONETIME, "One-time"), (MONTHLY, "Monthly")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=16, unique=True)  # used inside the access code
    name = models.CharField(max_length=80)
    price_ngn_kobo = models.PositiveBigIntegerField()  # money is always an integer
    price_esp = models.DecimalField(max_digits=18, decimal_places=4)  # fixed ESP price, no conversion
    is_recurring = models.BooleanField(default=False)
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    espees_product_sku = models.CharField(max_length=64, blank=True)
    espees_payment_ref = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    ACTIVE, EXPIRED, CANCELLED = "ACTIVE", "EXPIRED", "CANCELLED"
    STATUSES = [(ACTIVE, "Active"), (EXPIRED, "Expired"), (CANCELLED, "Cancelled")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATUSES, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "-expires_at"])]
