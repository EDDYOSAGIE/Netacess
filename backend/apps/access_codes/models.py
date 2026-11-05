import uuid

from django.db import models


class AccessCode(models.Model):
    ACTIVE, REVOKED, EXPIRED = "ACTIVE", "REVOKED", "EXPIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey("plans.Subscription", on_delete=models.PROTECT, related_name="codes")
    payment = models.OneToOneField("payments.Payment", on_delete=models.PROTECT, related_name="access_code")
    plan_code = models.CharField(max_length=16)
    code_hash = models.CharField(max_length=64, unique=True)  # lookup and uniqueness
    code_encrypted = models.TextField()  # so the customer can see it again in their profile
    status = models.CharField(max_length=10, default=ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
