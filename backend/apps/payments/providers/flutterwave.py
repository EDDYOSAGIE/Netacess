from decimal import Decimal

import requests
from django.conf import settings

from .base import Checkout, ProviderAdapter, ProviderError, Verification

API = "https://api.flutterwave.com/v3"


class FlutterwaveAdapter(ProviderAdapter):
    name = "flutterwave"

    def _headers(self):
        return {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}

    def create_checkout(self, payment, user, plan, redirect_url):
        body = {
            "tx_ref": payment.provider_reference,
            "amount": str(Decimal(payment.amount) / 100),  # kobo to naira for the API
            "currency": "NGN",
            "redirect_url": redirect_url,
            # card, bank transfer, USSD and bank account cover all Nigerian banks
            "payment_options": "card,banktransfer,ussd,account",
            "customer": {"email": user.email or f"{user.id}@netacess.invalid",
                         "phonenumber": user.phone, "name": user.full_name or user.phone},
            "customizations": {"title": "Netacess", "description": plan.name},
        }
        try:
            r = requests.post(f"{API}/payments", json=body, headers=self._headers(), timeout=15)
            r.raise_for_status()
            link = r.json()["data"]["link"]
        except (requests.RequestException, KeyError, ValueError) as e:
            raise ProviderError(f"Flutterwave checkout failed: {e}") from e
        return Checkout(reference=payment.provider_reference, url=link)

    def verify(self, payment):
        try:
            r = requests.get(f"{API}/transactions/verify_by_reference",
                             params={"tx_ref": payment.provider_reference},
                             headers=self._headers(), timeout=15)
            if r.status_code == 404:
                return Verification("NOT_FOUND", raw={})
            r.raise_for_status()
            data = r.json().get("data") or {}
        except (requests.RequestException, ValueError) as e:
            raise ProviderError(f"Flutterwave verify failed: {e}") from e
        status = {"successful": "SUCCESSFUL", "failed": "FAILED", "cancelled": "FAILED"}.get(
            data.get("status", ""), "PENDING")
        amount = Decimal(str(data["amount"])) * 100 if data.get("amount") is not None else None
        return Verification(status, amount, data.get("currency", ""), data)
