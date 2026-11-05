from decimal import Decimal
import uuid

import requests
from django.conf import settings

from .base import Checkout, ProviderAdapter, ProviderError, Verification

API = "https://api.espees.org/v2/payment"
PAY_URL = "https://payment.espees.org/pay/"


class EspeesAdapter(ProviderAdapter):
    """Hosted payment page. Espees has no webhook, so we confirm by polling."""
    name = "espees"

    def _headers(self):
        return {"Content-Type": "application/json", "x-api-key": settings.ESPEES_API_TOKEN}

    def create_plan_product(self, plan):
        sku = f"NETACESS-{plan.code}-{uuid.uuid4().hex[:8]}"
        body = {
            "product_sku": sku,
            "narration": f"Netacess {plan.name}",
            "price": float(plan.price_esp),
            "merchant_wallet": settings.ESPEES_MERCHANT_WALLET,
            "success_url": f"{settings.FRONTEND_URL}/?provider=espees&status=success",
            "fail_url": f"{settings.FRONTEND_URL}/?provider=espees&status=failed",
            "user_data": {"plan_code": plan.code},
        }
        try:
            r = requests.post(f"{API}/product", json=body, headers=self._headers(), timeout=15)
            r.raise_for_status()
            ref = r.json()["payment_ref"]
        except (requests.RequestException, KeyError, ValueError) as e:
            raise ProviderError(f"Espees product creation failed: {e}") from e
        return sku, ref

    def create_checkout(self, payment, user, plan, redirect_url):
        body = {
            "product_sku": str(payment.id).replace("-", ""),  # unique per attempt, so each month is a new link
            "narration": f"Netacess {plan.name}",
            "price": float(payment.amount),
            "merchant_wallet": settings.ESPEES_MERCHANT_WALLET,
            "success_url": f"{redirect_url}?status=success",
            "fail_url": f"{redirect_url}?status=failed",
            "user_data": {"payment_id": str(payment.id)},
        }
        try:
            r = requests.post(f"{API}/product", json=body, headers=self._headers(), timeout=15)
            r.raise_for_status()
            ref = r.json()["payment_ref"]
        except (requests.RequestException, KeyError, ValueError) as e:
            raise ProviderError(f"Espees product creation failed: {e}") from e
        return Checkout(reference=ref, url=PAY_URL + ref)

    def verify(self, payment):
        try:
            r = requests.post(f"{API}/confirm/", json={"payment_ref": payment.provider_reference},
                              headers=self._headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            raise ProviderError(f"Espees confirm failed: {e}") from e
        status = {"APPROVED": "SUCCESSFUL", "DECLINE": "FAILED", "PENDING": "PENDING",
                  "NOT FOUND": "NOT_FOUND"}.get(str(data.get("transaction_status", "")).upper(), "PENDING")
        price = data.get("price")
        return Verification(status, Decimal(str(price)) if price is not None else None, "ESP", data)
