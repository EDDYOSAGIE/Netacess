from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.plans.models import Plan


class Command(BaseCommand):
    help = "Create or update the two Netacess plans. ESP prices are fixed per plan, so you set them here."

    def add_arguments(self, p):
        p.add_argument("--esp-monthly", required=True)
        p.add_argument("--esp-onetime", required=True)
        p.add_argument("--monthly-days", type=int, default=30)
        p.add_argument("--onetime-days", type=int, default=30)  # confirm the real validity of the one-time plan

    def handle(self, *a, **o):
        Plan.objects.update_or_create(code="MONTHLY", defaults=dict(
            name="Monthly", price_ngn_kobo=50_000_00, price_esp=Decimal(o["esp_monthly"]),
            is_recurring=True, duration_days=o["monthly_days"]))
        Plan.objects.update_or_create(code="ONETIME", defaults=dict(
            name="One-time", price_ngn_kobo=100_000_00, price_esp=Decimal(o["esp_onetime"]),
            is_recurring=False, duration_days=o["onetime_days"]))
        self.stdout.write(self.style.SUCCESS("Plans ready"))
