import re
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.access_codes.models import AccessCode
from apps.access_codes.services import generate_code, validate_code
from apps.accounts.models import AuthToken, PhoneOTP, User
from apps.accounts.services import OTPError, request_otp, verify_otp
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.payments.providers.base import Checkout, ProviderError, Verification
from apps.payments.services import apply_verification, initiate_payment
from apps.plans.models import Plan, Subscription

CODE_RE = re.compile(r"^NETACESS_(MONTHLY|ONETIME)_\d{16}$")


TEST_KEY = Fernet.generate_key().decode()


def make_plans():
    m = Plan.objects.create(code="MONTHLY", name="Monthly", price_ngn_kobo=5_000_000,
                            price_esp=Decimal("12.5"), is_recurring=True)
    o = Plan.objects.create(code="ONETIME", name="One-time", price_ngn_kobo=10_000_000,
                            price_esp=Decimal("25"), is_recurring=False)
    return m, o


def fake_checkout(self, payment, user, plan, redirect_url):
    ref = payment.provider_reference if payment.provider == "flutterwave" else "ESPREF" + payment.id.hex[:8]
    return Checkout(reference=ref, url=f"https://pay.example/{ref}")


@override_settings(ACCESS_CODE_ENC_KEY=TEST_KEY, DEBUG=True, SMS_PROVIDER="console",
                   DEMO_MODE=False, DEMO_PHONE_ALLOWLIST=set())
@patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", fake_checkout)
@patch("apps.payments.providers.espees.EspeesAdapter.create_checkout", fake_checkout)
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.monthly, self.onetime = make_plans()
        self.user = User.objects.create_user("+2348012345678", is_phone_verified=True)

    def pay(self, provider="flutterwave", plan=None, key="k1"):
        return initiate_payment(self.user, plan or self.monthly, provider, key)

    def test_code_format(self):
        for _ in range(50):
            self.assertRegex(generate_code("MONTHLY"), CODE_RE)
            self.assertRegex(generate_code("ONETIME"), CODE_RE)

    def test_successful_payment_issues_one_valid_code(self):
        _, p = self.pay()
        v = Verification("SUCCESSFUL", Decimal(p.amount), "NGN")
        apply_verification(p.id, v, "webhook")
        apply_verification(p.id, v, "poll")  # duplicate delivery
        apply_verification(p.id, v, "poll")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.SUCCESSFUL)
        self.assertEqual(AccessCode.objects.count(), 1)
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(kind="payment_received").count(), 1)
        from apps.access_codes.services import decrypt
        code = decrypt(AccessCode.objects.get())
        self.assertRegex(code, CODE_RE)
        self.assertIn("_MONTHLY_", code)
        self.assertIsNotNone(validate_code(code))
        self.assertIsNone(validate_code("NETACESS_MONTHLY_0000000000000000"))

    def test_plan_name_is_in_code(self):
        _, p = self.pay(plan=self.onetime, key="k2")
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal(p.amount), "NGN"), "poll")
        from apps.access_codes.services import decrypt
        self.assertIn("NETACESS_ONETIME_", decrypt(AccessCode.objects.get()))

    @override_settings(ESPEES_CHECKOUT_READY=True)
    def test_espees_uses_esp_amount_only(self):
        from apps.adminops.providers import set_enabled
        set_enabled("espees", True)
        order, p = self.pay("espees")
        self.assertEqual(p.currency, "ESP")
        self.assertEqual(p.amount, Decimal("12.5"))
        self.assertIsNone(order.amount_ngn_kobo)
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal("12.5"), "ESP"), "poll")
        self.assertEqual(AccessCode.objects.count(), 1)

    def test_wrong_amount_goes_to_review_and_no_code(self):
        _, p = self.pay()
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal("100"), "NGN"), "webhook")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.NEEDS_REVIEW)
        self.assertEqual(AccessCode.objects.count(), 0)

    def test_failed_payment_gives_no_code(self):
        _, p = self.pay()
        apply_verification(p.id, Verification("FAILED"), "poll")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.FAILED)
        self.assertEqual(AccessCode.objects.count(), 0)

    def test_late_success_after_expiry_still_honoured(self):
        _, p = self.pay()
        Payment.objects.filter(pk=p.pk).update(status=Payment.EXPIRED)
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal(p.amount), "NGN"), "poll")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.SUCCESSFUL)
        self.assertEqual(AccessCode.objects.count(), 1)

    def test_same_idempotency_key_does_not_create_second_payment(self):
        o1, p1 = self.pay(key="same")
        o2, p2 = self.pay(key="same")
        self.assertEqual(o1.id, o2.id)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(Payment.objects.count(), 1)

    def test_renewal_extends_validity(self):
        _, p1 = self.pay(key="a")
        apply_verification(p1.id, Verification("SUCCESSFUL", Decimal(p1.amount), "NGN"), "poll")
        first = Subscription.objects.get()
        _, p2 = self.pay(key="b")
        apply_verification(p2.id, Verification("SUCCESSFUL", Decimal(p2.amount), "NGN"), "poll")
        second = Subscription.objects.exclude(pk=first.pk).get()
        self.assertEqual(second.starts_at, first.expires_at)
        self.assertEqual(AccessCode.objects.count(), 2)

    def test_checkout_failure_marks_failed(self):
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout",
                   side_effect=ProviderError("down")):
            with self.assertRaises(ProviderError):
                self.pay(key="z")
        self.assertEqual(Payment.objects.get().status, Payment.FAILED)


@override_settings(ACCESS_CODE_ENC_KEY=TEST_KEY, DEBUG=True, SMS_PROVIDER="console",
                   SMS_ALLOWLIST=[], DEMO_MODE=False, DEMO_PHONE_ALLOWLIST=set(),
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", fake_checkout)
class ApiTests(TestCase):
    def setUp(self):
        call_command("createcachetable", verbosity=0)
        self.monthly, _ = make_plans()
        self.c = APIClient()

    def login(self):
        from django.core import mail
        with patch("apps.sms.otp.send_sms_task.delay") as sms:
            sent = self.c.post("/api/auth/otp/send", {
                "phone": "08012345678", "email": "customer@example.com", "purpose": "signup",
            }, format="json")
            self.assertEqual(sent.status_code, 200, sent.data)
            self.assertNotIn("code", sent.data)
            self.assertFalse(sms.called)
            code = re.search(r"code is (\d{6})", mail.outbox[-1].body).group(1)
        r = self.c.post("/api/auth/otp/verify", {
            "phone": "08012345678", "email": "customer@example.com", "purpose": "signup", "code": code,
            "password": "valid-password-123", "policies_accepted": True,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["token"])
        return User.objects.get()

    def test_signup_pay_and_see_code(self):
        user = self.login()
        self.assertEqual(user.phone, "+2348012345678")
        r = self.c.post("/api/orders", {"plan": "MONTHLY", "provider": "flutterwave", "idempotency_key": "x1"},
                        format="json")
        self.assertEqual(r.status_code, 201)
        pid = r.data["payment"]["id"]
        self.assertIsNone(r.data["payment"]["access_code"])
        ok = Verification("SUCCESSFUL", Decimal("5000000"), "NGN", {
            "payment_type": "card",
            "card": {"type": "VISA", "last_4digits": "4242", "first_6digits": "411111", "token": "provider-token"},
        })
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.verify", return_value=ok):
            r = self.c.get(f"/api/payments/{pid}")
        self.assertEqual(r.data["status"], "SUCCESSFUL")
        self.assertRegex(r.data["access_code"], CODE_RE)
        me = self.c.get("/api/me").data
        self.assertEqual(me["subscription"]["plan_code"], "MONTHLY")
        self.assertEqual(self.c.get("/api/me/codes").data[0]["code"], r.data["access_code"])
        tx = self.c.get("/api/me/transactions?status=SUCCESSFUL").data
        self.assertEqual(len(tx["results"]), 1)
        self.assertEqual(tx["results"][0]["card_brand"], "VISA")
        self.assertEqual(tx["results"][0]["card_last4"], "4242")
        from apps.payments.models import PaymentEvent
        event_payload = PaymentEvent.objects.get(payment_id=pid, event_type="verify_successful").payload
        self.assertNotIn("token", event_payload["card"])
        self.assertNotIn("first_6digits", event_payload["card"])
        n = self.c.get("/api/me/notifications").data
        self.assertEqual(n["unread_count"], 2)
        self.c.post("/api/me/notifications/read", {}, format="json")
        self.assertEqual(self.c.get("/api/me/notifications").data["unread_count"], 0)

    def test_requires_login(self):
        self.assertEqual(self.c.post("/api/orders", {}, format="json").status_code, 401)

    def test_idle_token_expires_after_one_hour(self):
        user = User.objects.create_user("+2348012345678", email="idle@example.com")
        token = AuthToken.issue(user)
        token_hash = AuthToken.hash_key(token)
        AuthToken.objects.filter(key_hash=token_hash).update(
            last_used_at=timezone.now() - timedelta(hours=1, seconds=1),
        )
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.c.get("/api/me")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(AuthToken.objects.filter(key_hash=token_hash).exists())

    def test_active_plan_catalog_is_shared_and_deactivated_plan_is_hidden(self):
        self.login()
        plan = Plan.objects.get(code="MONTHLY")
        first = self.c.get("/api/plans")
        self.assertIn(str(plan.id), [item["id"] for item in first.data])
        plan.is_active = False
        plan.save(update_fields=["is_active"])
        self.assertNotIn(str(plan.id), [item["id"] for item in self.c.get("/api/plans").data])

    def test_provider_down_returns_fallback_message(self):
        self.login()
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout",
                   side_effect=ProviderError("x")):
            r = self.c.post("/api/orders", {"plan": "MONTHLY", "provider": "flutterwave", "idempotency_key": "y"},
                            format="json")
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.data["error"], "provider_unavailable")

    @override_settings(FLUTTERWAVE_WEBHOOK_HASH="secret")
    def test_webhook_needs_valid_hash(self):
        self.assertEqual(self.c.post("/api/webhooks/flutterwave", {}, format="json").status_code, 401)
        r = self.c.post("/api/webhooks/flutterwave", {"data": {"tx_ref": "none"}}, format="json",
                        HTTP_VERIF_HASH="secret")
        self.assertEqual(r.status_code, 200)


class OtpTests(TestCase):
    @patch("apps.accounts.services.send_sms")
    def test_rules(self, sms):
        phone = "+2348099999999"
        request_otp(phone)
        with self.assertRaises(OTPError) as e:  # resend after 60 seconds only
            request_otp(phone)
        self.assertEqual(e.exception.code, "too_soon")
        otp = PhoneOTP.objects.get()
        for _ in range(5):
            with self.assertRaises(OTPError):
                verify_otp(phone, "000000")
        with self.assertRaises(OTPError) as e:
            verify_otp(phone, "000000")
        self.assertEqual(e.exception.code, "too_many_attempts")
        self.assertNotIn("000000", otp.code_hash)

    @patch("apps.accounts.services.send_sms")
    def test_expired(self, sms):
        phone = "+2348099999998"
        request_otp(phone)
        PhoneOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(OTPError) as e:
            verify_otp(phone, "123456")
        self.assertEqual(e.exception.code, "expired")

    @patch("apps.accounts.services.send_sms")
    def test_hourly_limit(self, sms):
        phone = "+2348099999997"
        for _ in range(3):
            request_otp(phone)
            PhoneOTP.objects.filter(phone=phone).update(created_at=timezone.now() - timedelta(minutes=30))
        with self.assertRaises(OTPError) as e:
            request_otp(phone)
        self.assertEqual(e.exception.code, "rate_limited")


@override_settings(ACCESS_CODE_ENC_KEY=TEST_KEY)
@patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", fake_checkout)
class FallbackTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.monthly, _ = make_plans()
        self.user = User.objects.create_user("+2348055550000", is_phone_verified=True)

    def test_can_retry_with_same_key_after_failure(self):
        _, p = initiate_payment(self.user, self.monthly, "flutterwave", "k")
        apply_verification(p.id, Verification("FAILED"), "poll")
        _, p2 = initiate_payment(self.user, self.monthly, "flutterwave", "k")
        self.assertNotEqual(p.id, p2.id)
        self.assertEqual(p2.status, Payment.PENDING)

    def test_circuit_breaker_opens_after_repeated_failures(self):
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout",
                   side_effect=ProviderError("down")) as m:
            for i in range(5):
                with self.assertRaises(ProviderError):
                    initiate_payment(self.user, self.monthly, "flutterwave", f"b{i}")
            with self.assertRaises(ProviderError):
                initiate_payment(self.user, self.monthly, "flutterwave", "b-next")
            self.assertEqual(m.call_count, 5)  # the sixth never reached the provider

    def test_review_payment_not_rechecked_and_no_event_spam(self):
        _, p = initiate_payment(self.user, self.monthly, "flutterwave", "r")
        bad = Verification("SUCCESSFUL", Decimal("1"), "NGN")
        for _ in range(4):
            apply_verification(p.id, bad, "poll")
        self.assertEqual(p.events.filter(event_type="amount_mismatch").count(), 1)

    def test_other_currency_goes_to_review(self):
        _, p = initiate_payment(self.user, self.monthly, "flutterwave", "usd")
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal(p.amount), "USD"), "webhook")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.NEEDS_REVIEW)
        self.assertEqual(AccessCode.objects.count(), 0)

    def test_admin_approve_issues_code_once(self):
        from apps.payments.services import admin_approve, admin_mark
        staff = User.objects.create_user("+2348055550001", is_staff=True)
        _, p = initiate_payment(self.user, self.monthly, "flutterwave", "adm")
        apply_verification(p.id, Verification("SUCCESSFUL", Decimal("1"), "NGN"), "poll")
        admin_approve(p.id, staff)
        admin_approve(p.id, staff)
        self.assertEqual(AccessCode.objects.count(), 1)
        with self.assertRaises(ValueError):
            admin_mark(p.id, Payment.FAILED, staff)  # a successful payment can only be refunded
        admin_mark(p.id, Payment.REFUNDED, staff)

    def test_reconcile_picks_up_missed_webhook_and_expires_stale(self):
        from apps.payments.tasks import reconcile_pending
        _, paid = initiate_payment(self.user, self.monthly, "flutterwave", "m1")
        _, stale = initiate_payment(self.user, self.monthly, "flutterwave", "m2")
        Payment.objects.filter(pk=stale.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        def fake_verify(self_, payment):
            if payment.pk == paid.pk:
                return Verification("SUCCESSFUL", Decimal(payment.amount), "NGN")
            return Verification("PENDING")
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.verify", fake_verify):
            reconcile_pending()
        paid.refresh_from_db(); stale.refresh_from_db()
        self.assertEqual(paid.status, Payment.SUCCESSFUL)
        self.assertEqual(stale.status, Payment.EXPIRED)
        self.assertEqual(AccessCode.objects.count(), 1)

    def test_provider_error_during_poll_does_not_change_state(self):
        _, p = initiate_payment(self.user, self.monthly, "flutterwave", "e")
        from apps.payments.services import check_payment
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.verify", side_effect=ProviderError("x")):
            with self.assertRaises(ProviderError):
                check_payment(p.id)
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.PENDING)
