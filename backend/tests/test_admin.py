from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.access_codes.models import AccessCode
from apps.accounts.models import AuthToken, User
from apps.adminops.models import AuditLog
from apps.payments.models import Payment
from apps.payments.providers.base import ProviderError, Verification
from apps.payments.services import apply_verification, initiate_payment

from .test_flow import TEST_KEY, fake_checkout, make_plans


def client_for(user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION="Bearer " + AuthToken.issue(user))
    return c


@override_settings(ACCESS_CODE_ENC_KEY=TEST_KEY)
class AdminApiTests(TestCase):
    def setUp(self):
        for target in ("flutterwave.FlutterwaveAdapter", "espees.EspeesAdapter"):
            pt = patch(f"apps.payments.providers.{target}.create_checkout", fake_checkout)
            pt.start()
            self.addCleanup(pt.stop)
        cache.clear()
        self.monthly, _ = make_plans()
        self.cust = User.objects.create_user("+2348060000001", full_name="Cust", is_phone_verified=True)
        self.staff = User.objects.create_user("+2348060000002", full_name="Staff", is_staff=True)
        _, self.p = initiate_payment(self.cust, self.monthly, "flutterwave", "a1")
        apply_verification(self.p.id, Verification("SUCCESSFUL", Decimal("100"), "NGN"), "webhook")  # mismatch
        self.admin = client_for(self.staff)

    def test_customers_cannot_use_admin_api(self):
        c = client_for(self.cust)
        for url in ("/api/admin/summary", "/api/admin/payments", "/api/admin/audit"):
            self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(APIClient().get("/api/admin/summary").status_code, 401)

    def test_review_queue_shows_issue_and_received(self):
        r = self.admin.get("/api/admin/payments?status=NEEDS_REVIEW").data["results"]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["issue"], "Amount mismatch")
        self.assertEqual(r[0]["received"], "100 NGN")
        self.assertEqual(r[0]["user_phone"], "+2348060000001")
        self.assertEqual(self.admin.get("/api/admin/payments?q=0001").data["results"][0]["id"], str(self.p.id))

    def test_summary(self):
        s = self.admin.get("/api/admin/summary").data
        self.assertEqual(s["needs_review"], 1)
        self.assertEqual({p["name"] for p in s["providers"]}, {"flutterwave", "espees"})

    def test_staff_can_update_espees_conversion_rate(self):
        path = "/api/admin/currency-rate"
        self.assertEqual(APIClient().get(path).status_code, 401)
        self.assertEqual(client_for(self.cust).get(path).status_code, 403)
        initial = self.admin.get(path)
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.data["esp_to_ngn"], Decimal("4000.0000"))

        updated = self.admin.patch(path, {"esp_to_ngn": "4200.50"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["esp_to_ngn"], Decimal("4200.5000"))
        audit = AuditLog.objects.get(action="currency_rate_updated")
        self.assertEqual(audit.actor, self.staff)
        self.assertEqual(audit.target_id, "esp_to_ngn")

        plan = APIClient().get("/api/plans").data[0]
        self.assertEqual(plan["price_esp_ngn_kobo"], Decimal("5250625"))

    def test_currency_rate_rejects_non_positive_values(self):
        response = self.admin.patch("/api/admin/currency-rate", {"esp_to_ngn": "0"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_approve_needs_reason_then_issues_code_and_audits(self):
        url = f"/api/admin/payments/{self.p.id}/action"
        r = self.admin.post(url, {"action": "approve"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["error"], "reason_required")
        self.assertEqual(AccessCode.objects.count(), 0)
        r = self.admin.post(url, {"action": "approve", "reason": "Seen in Flutterwave dashboard"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "SUCCESSFUL")
        self.assertTrue(r.data["has_code"])
        self.assertEqual(AccessCode.objects.count(), 1)
        log = AuditLog.objects.get()
        self.assertEqual((log.actor, log.action, log.reason), (self.staff, "approve", "Seen in Flutterwave dashboard"))
        self.assertTrue(any(e["event_type"] == "approved" and e["payload"]["reason"] for e in r.data["events"]))
        # a second approve changes nothing
        self.admin.post(url, {"action": "approve", "reason": "again"}, format="json")
        self.assertEqual(AccessCode.objects.count(), 1)

    def test_refund_from_review_then_locked(self):
        url = f"/api/admin/payments/{self.p.id}/action"
        r = self.admin.post(url, {"action": "refund", "reason": "Wrong amount, returning money"}, format="json")
        self.assertEqual(r.data["status"], "REFUNDED")
        self.assertEqual(AccessCode.objects.count(), 0)  # no code for refunded money
        r = self.admin.post(url, {"action": "fail", "reason": "oops"}, format="json")
        self.assertEqual(r.status_code, 409)  # a refunded payment is final

    def test_fail_from_review(self):
        r = self.admin.post(f"/api/admin/payments/{self.p.id}/action", {"action": "fail", "reason": "Not received"}, format="json")
        self.assertEqual(r.data["status"], "FAILED")

    def test_recheck_provider_error_is_reported(self):
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.verify", side_effect=ProviderError("x")):
            r = self.admin.post(f"/api/admin/payments/{self.p.id}/action", {"action": "recheck"}, format="json")
        self.assertEqual(r.status_code, 502)

    @override_settings(ESPEES_CHECKOUT_READY=True)
    def test_switching_provider_off_blocks_checkout_and_hides_it(self):
        self.assertFalse(APIClient().get("/api/providers").data["espees"])
        self.admin.post("/api/admin/providers/espees", {"enabled": True, "reason": "Enable for provider test"}, format="json")
        self.assertTrue(APIClient().get("/api/providers").data["espees"])
        r = self.admin.post("/api/admin/providers/espees", {"enabled": False}, format="json")
        self.assertEqual(r.status_code, 400)  # reason needed
        self.admin.post("/api/admin/providers/espees", {"enabled": False, "reason": "Espees maintenance"}, format="json")
        self.assertFalse(APIClient().get("/api/providers").data["espees"])
        with self.assertRaises(ProviderError):
            initiate_payment(self.cust, self.monthly, "espees", "x1")
        c = client_for(self.cust)
        r = c.post("/api/orders", {"plan": "MONTHLY", "provider": "espees", "idempotency_key": "x2"}, format="json")
        self.assertEqual(r.status_code, 502)
        self.admin.post("/api/admin/providers/espees", {"enabled": True, "reason": "Back up"}, format="json")
        initiate_payment(self.cust, self.monthly, "espees", "x3")
        self.assertEqual(AuditLog.objects.filter(target_type="provider").count(), 3)
        self.assertEqual(len(self.admin.get("/api/admin/audit").data["results"]), 3)

    def test_admin_can_create_and_edit_plans(self):
        data = {"name": "Weekly", "price_ngn_kobo": 250000,
                "price_esp": "2.5", "is_recurring": False, "duration_days": 7, "is_active": True}
        created = self.admin.post("/api/admin/plans", data, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertRegex(created.data["code"], r"^WEEKLY_[A-F0-9]{6}$")
        plan_id = created.data["id"]
        updated = self.admin.patch(f"/api/admin/plans/{plan_id}", {"name": "Weekly Plus", "price_esp": "3.0"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["name"], "Weekly Plus")
        self.assertEqual(updated.data["price_esp"], "3.0000")
        self.assertIn(created.data["code"], [p["code"] for p in APIClient().get("/api/plans").data])

    @patch("apps.payments.providers.espees.EspeesAdapter.create_plan_product", return_value=("SKU-TEST", "REF-TEST"))
    def test_admin_can_create_espees_product_for_plan(self, create_product):
        response = self.admin.post(f"/api/admin/plans/{self.monthly.id}/espees-product", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["espees_product_sku"], "SKU-TEST")
        self.assertEqual(response.data["espees_payment_ref"], "REF-TEST")
        create_product.assert_called_once()

    @override_settings(ESPEES_CHECKOUT_READY=False)
    def test_espees_customer_checkout_cannot_be_enabled_while_incomplete(self):
        response = self.admin.post("/api/admin/providers/espees", {"enabled": True, "reason": "test"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(APIClient().get("/api/providers").data["espees"])


class PreferenceTests(TestCase):
    def test_save_and_default_preference(self):
        u = User.objects.create_user("+2348060000009", is_phone_verified=True)
        c = client_for(u)
        self.assertEqual(c.get("/api/me").data["preferred_provider"], "")
        r = c.patch("/api/me", {"preferred_provider": "espees"}, format="json")
        self.assertEqual(r.data["preferred_provider"], "espees")
        self.assertEqual(c.patch("/api/me", {"preferred_provider": "paypal"}, format="json").status_code, 400)
        self.assertFalse(c.get("/api/me").data["is_staff"])
