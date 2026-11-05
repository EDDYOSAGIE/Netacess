import hashlib
import io
from contextlib import redirect_stdout
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import PolicyAcceptance, User
from apps.accounts.policies import PRIVACY_VERSION, TERMS_VERSION
from apps.payments.models import Payment
from apps.payments.providers.base import Checkout, Verification
from apps.payments.services import apply_verification, initiate_payment
from apps.plans.models import Plan, Subscription
from apps.sms.models import SMSLog
from apps.sms.otp import OTPError, _cooldown_key, _otp_key, send_otp, verify_otp
from apps.sms.providers import ConsoleProvider, SMSError, TermiiProvider, normalize_ng
from apps.sms.tasks import send_sms_task


@override_settings(DEBUG=True, SMS_PROVIDER="console", SMS_ALLOWLIST=[], DEMO_MODE=False,
                   DEMO_PHONE_ALLOWLIST=set())
class SMSOTPTests(TestCase):
    def setUp(self):
        call_command("createcachetable", verbosity=0)
        cache.clear()
        self.client = APIClient()

    def test_normalize_ng(self):
        self.assertEqual(normalize_ng("+234 801-234-5678"), "2348012345678")
        self.assertEqual(normalize_ng("08012345678"), "2348012345678")
        with self.assertRaises(SMSError):
            normalize_ng("12345")

    def test_console_prints_otp_but_redacts_access_code(self):
        output = io.StringIO()
        with redirect_stdout(output):
            ConsoleProvider().send("2348012345678", "Your code is 123456. NETACESS_MONTHLY_1234567890123456")
        self.assertIn("Your code is 123456", output.getvalue())
        self.assertNotIn("NETACESS_MONTHLY_", output.getvalue())

    @override_settings(SMS_ALLOWLIST=["2348012345678"])
    def test_allowlist_blocks_unapproved_real_sends(self):
        with patch("apps.sms.providers.requests.post") as post:
            with self.assertRaises(SMSError):
                TermiiProvider().send("08099999999", "test")
        post.assert_not_called()

    @patch("apps.sms.providers.requests.post")
    @override_settings(SMS_PROVIDER="termii", TERMII_API_KEY="test-key", SMS_ALLOWLIST=[])
    def test_termii_request_and_error_logging(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"code": "ok", "message_id": "m-1"}
        self.assertEqual(TermiiProvider().send("08012345678", "hello"), "m-1")
        self.assertEqual(post.call_args.kwargs["timeout"], 10)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["channel"], "dnd")
        self.assertEqual(body["from"], "N-Alert")
        post.return_value.status_code = 400
        post.return_value.json.return_value = {"message": "sender rejected"}
        with self.assertLogs("apps.sms.providers", level="ERROR") as captured:
            with self.assertRaises(SMSError):
                TermiiProvider().send("08012345678", "hello")
        self.assertIn("sender rejected", captured.output[0])
        self.assertNotIn("test-key", captured.output[0])

    @patch("apps.sms.tasks.get_provider")
    def test_task_is_idempotent(self, provider):
        provider.return_value.send.return_value = "msg-1"
        send_sms_task.run("2348012345678", "hello", "test", "unique-ref")
        send_sms_task.run("2348012345678", "hello", "test", "unique-ref")
        self.assertEqual(provider.return_value.send.call_count, 1)
        self.assertEqual(SMSLog.objects.get(reference="unique-ref").status, SMSLog.SENT)

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_otp_success_wrong_expired_attempts_and_purpose(self, send_task):
        phone = "08012345678"
        code, sms_sent, error = send_otp(phone, "signup", "127.0.0.1")
        self.assertTrue(sms_sent)
        self.assertEqual(error, "")
        send_task.assert_called_once()
        self.assertEqual(verify_otp(phone, "signup", code), "2348012345678")
        with self.assertRaises(OTPError):
            verify_otp(phone, "signup", code)

        cache.delete(_cooldown_key("2348012345678", "signup"))
        code, _, _ = send_otp(phone, "signup", "127.0.0.1")
        with self.assertRaises(OTPError):
            verify_otp(phone, "login", code)
        wrong_code = "000000" if code != "000000" else "000001"
        for _ in range(5):
            with self.assertRaises(OTPError):
                verify_otp(phone, "signup", wrong_code)
        with self.assertRaises(OTPError):
            verify_otp(phone, "signup", code)

        cache.delete(_cooldown_key("2348012345678", "signup"))
        code, _, _ = send_otp("08012345679", "signup", "127.0.0.1")
        record = cache.get(_otp_key("2348012345679", "signup"))
        record["expires_at"] = timezone.now().timestamp() - 1
        cache.set(_otp_key("2348012345679", "signup"), record, timeout=300)
        with self.assertRaises(OTPError):
            verify_otp("08012345679", "signup", code)

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_resend_cooldown(self, send_task):
        send_otp("08012345678", "signup", "127.0.0.1")
        with self.assertRaises(SMSError):
            send_otp("08012345678", "signup", "127.0.0.1")

    @override_settings(DEMO_MODE=True, DEMO_PHONE_ALLOWLIST={"2348012345678"})
    @patch("apps.sms.otp.send_sms_task.delay")
    def test_demo_response_includes_code(self, delay):
        response = self.client.post("/api/auth/otp/send", {"phone": "08012345678", "purpose": "signup"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data["code"], r"^\d{6}$")
        self.assertTrue(response.data["sms_sent"])
        self.assertIn(response.data["code"], delay.call_args.args[1])

    @override_settings(DEBUG=False, DEMO_MODE=True, SMS_PROVIDER="console",
                       DEMO_PHONE_ALLOWLIST={"2348012345678"}, USE_REDIS=False,
                       CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
    @patch("apps.sms.tasks.get_provider")
    def test_deployed_demo_allows_only_configured_phone(self, provider):
        provider.return_value.send.return_value = "console-fake-id"
        allowed = self.client.post("/api/auth/otp/send", {
            "phone": "+2348012345678", "purpose": "signup",
        }, format="json")
        self.assertEqual(allowed.status_code, 200)
        self.assertRegex(allowed.data["code"], r"^\d{6}$")

        rejected = self.client.post("/api/auth/otp/send", {
            "phone": "+2348099999999", "purpose": "signup",
        }, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.assertNotIn("code", rejected.data)
        self.assertEqual(provider.return_value.send.call_count, 1)

    @override_settings(DEMO_MODE=True, DEMO_PHONE_ALLOWLIST={"2348012345678"},
                       USE_REDIS=False, CELERY_TASK_ALWAYS_EAGER=True,
                       CELERY_TASK_EAGER_PROPAGATES=True, SMS_PROVIDER="termii",
                       TERMII_API_KEY="do-not-return-or-log")
    @patch("apps.sms.tasks.get_provider", side_effect=SMSError("sender rejected"))
    def test_provider_failure_in_demo_returns_code_and_keeps_otp_verifiable(self, provider):
        with self.assertLogs("apps.sms", level="ERROR") as captured:
            response = self.client.post("/api/auth/otp/send", {
                "phone": "08012345678", "purpose": "signup",
            }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["sms_sent"])
        self.assertRegex(response.data["code"], r"^\d{6}$")
        self.assertNotIn("do-not-return-or-log", response.content.decode())
        self.assertNotIn("do-not-return-or-log", "\n".join(captured.output))
        verified = self.client.post("/api/auth/otp/verify", {
            "phone": "08012345678", "purpose": "signup", "code": response.data["code"],
            "password": "valid-password-123", "policies_accepted": True,
        }, format="json")
        self.assertEqual(verified.status_code, 200)

    @override_settings(DEMO_MODE=False, USE_REDIS=False, CELERY_TASK_ALWAYS_EAGER=True,
                       CELERY_TASK_EAGER_PROPAGATES=True, SMS_PROVIDER="termii",
                       TERMII_API_KEY="do-not-return-or-log")
    @patch("apps.sms.tasks.get_provider", side_effect=SMSError("sender rejected"))
    def test_provider_failure_outside_demo_returns_generic_502_and_keeps_otp(self, provider):
        with self.assertLogs("apps.sms", level="ERROR") as captured:
            response = self.client.post("/api/auth/otp/send", {
                "phone": "08012345678", "purpose": "signup",
            }, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data, {
            "error": "sms_unavailable", "message": "Could not send SMS right now",
        })
        self.assertNotIn("code", response.data)
        self.assertNotIn("do-not-return-or-log", response.content.decode())
        self.assertNotIn("do-not-return-or-log", "\n".join(captured.output))
        self.assertIsNotNone(cache.get(_otp_key("2348012345678", "signup")))

    @override_settings(USE_REDIS=False)
    @patch("apps.sms.tasks.get_provider", side_effect=SMSError("provider down"))
    @patch("apps.sms.tasks.send_sms_task.retry")
    def test_eager_send_failure_marks_failed_without_retry(self, retry, provider):
        result = send_sms_task.run("2348012345678", "hello", "test", "eager-failure")
        self.assertEqual(result["status"], SMSLog.FAILED)
        self.assertEqual(SMSLog.objects.get(reference="eager-failure").status, SMSLog.FAILED)
        retry.assert_not_called()

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_non_demo_response_omits_code_and_success_verify_issues_token(self, delay):
        response = self.client.post("/api/auth/otp/send", {"phone": "08012345678", "purpose": "signup"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("code", response.data)
        sent_code = delay.call_args.args[1].split(" is ")[1].split(".")[0]
        verified = self.client.post("/api/auth/otp/verify", {
            "phone": "08012345678", "purpose": "signup", "code": sent_code,
            "password": "valid-password-123", "policies_accepted": True,
        }, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertIn("token", verified.data)
        acceptance = PolicyAcceptance.objects.get(user__phone="+2348012345678")
        self.assertEqual(acceptance.terms_version, TERMS_VERSION)
        self.assertEqual(acceptance.privacy_version, PRIVACY_VERSION)

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_signup_requires_policy_acceptance_without_consuming_otp(self, delay):
        response = self.client.post("/api/auth/otp/send", {
            "phone": "08012345678", "purpose": "signup",
        }, format="json")
        sent_code = delay.call_args.args[1].split(" is ")[1].split(".")[0]
        payload = {
            "phone": "08012345678", "purpose": "signup", "code": sent_code,
            "password": "valid-password-123",
        }

        rejected = self.client.post("/api/auth/otp/verify", payload, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(User.objects.exists())
        self.assertFalse(PolicyAcceptance.objects.exists())

        payload["policies_accepted"] = True
        accepted = self.client.post("/api/auth/otp/verify", payload, format="json")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(PolicyAcceptance.objects.count(), 1)

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_login_sends_and_verifies_otp_for_existing_staff_user(self, send_task):
        staff_user = User.objects.create_user(
            "+2348012345678", "staff-password-123", is_staff=True, is_phone_verified=True,
        )
        sent = self.client.post("/api/auth/otp/send", {
            "phone": "08012345678", "purpose": "login",
        }, format="json")
        self.assertEqual(sent.status_code, 200)
        code = send_task.call_args.args[1].split(" is ")[1].split(".")[0]

        verified = self.client.post("/api/auth/otp/verify", {
            "phone": "+2348012345678", "purpose": "login", "code": code,
        }, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.data["user"]["id"], str(staff_user.id))
        self.assertIn("token", verified.data)

    @patch("apps.sms.otp.send_sms_task.delay")
    def test_login_unknown_phone_reports_missing_account_before_sending_otp(self, send_task):
        sent = self.client.post("/api/auth/otp/send", {
            "phone": "08012345678", "purpose": "login",
        }, format="json")
        self.assertEqual(sent.status_code, 404)
        self.assertEqual(sent.data["error"], "account_not_found")
        send_task.assert_not_called()

        verified = self.client.post("/api/auth/otp/verify", {
            "phone": "08012345678", "purpose": "login", "code": "123456",
        }, format="json")
        self.assertEqual(verified.status_code, 404)
        self.assertEqual(verified.data["error"], "account_not_found")

    def test_send_throttled_by_ip(self):
        with patch("apps.sms.otp.send_sms_task.delay"):
            cache.clear()
            for index in range(3):
                response = self.client.post("/api/auth/otp/send", {
                    "phone": f"0801234567{index}", "purpose": "signup",
                }, format="json")
                self.assertEqual(response.status_code, 200)
            response = self.client.post("/api/auth/otp/send", {
                "phone": "08012345679", "purpose": "signup",
            }, format="json")
        self.assertEqual(response.status_code, 429)

    @patch("apps.sms.throttles.cache.get", side_effect=RuntimeError("cache unavailable"))
    def test_otp_send_returns_503_when_throttle_cache_is_unavailable(self, cache_get):
        response = self.client.post("/api/auth/otp/send", {
            "phone": "08012345678", "purpose": "signup",
        }, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"].code, "cache_unavailable")
        cache_get.assert_called_once()

    def test_send_throttled_by_phone(self):
        with patch("apps.sms.otp.send_sms_task.delay"):
            for _ in range(3):
                response = self.client.post("/api/auth/otp/send", {
                    "phone": "08012345678", "purpose": "signup",
                }, format="json")
                self.assertEqual(response.status_code, 200)
                cache.delete("sms:cooldown:signup:" + hashlib.sha256(b"2348012345678").hexdigest())
            response = self.client.post("/api/auth/otp/send", {
                "phone": "08012345678", "purpose": "signup",
            }, format="json")
        self.assertEqual(response.status_code, 429)


@override_settings(DEBUG=True, SMS_PROVIDER="console", SMS_ALLOWLIST=[])
class PaymentSMSTests(TestCase):
    def test_payment_sms_is_queued_once_after_verified_fulfilment(self):
        user = User.objects.create_user("+2348012345678", is_phone_verified=True)
        plan = Plan.objects.create(code="MONTHLY", name="Monthly", price_ngn_kobo=5000000,
                                   price_esp=Decimal("12.5"), duration_days=30)
        checkout = Checkout(reference="tx-sms-test", url="https://pay.example/tx-sms-test")
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", return_value=checkout):
            _, payment = initiate_payment(user, plan, "flutterwave", "sms-pay")
        with patch("apps.sms.tasks.send_sms_task.delay") as sms:
            with self.captureOnCommitCallbacks(execute=True):
                verification = Verification("SUCCESSFUL", Decimal("5000000"), "NGN")
                apply_verification(payment.id, verification, "webhook")
                apply_verification(payment.id, verification, "poll")
        self.assertEqual(sms.call_count, 1)
        self.assertEqual(sms.call_args.args[2:], ("access_code", f"access-{payment.provider_reference}"))
        self.assertIn("NETACESS_MONTHLY_", sms.call_args.args[1])


class ExpiryReminderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("+2348012345678", is_phone_verified=True)
        self.plan = Plan.objects.create(code="MONTHLY", name="Monthly", price_ngn_kobo=5000000,
                                        price_esp=Decimal("12.5"))

    @override_settings(USE_REDIS=True)
    def test_reminder_queues_with_stable_reference(self):
        expires_at = timezone.now() + timedelta(days=2) - timedelta(minutes=30)
        subscription = Subscription.objects.create(
            user=self.user, plan=self.plan, starts_at=timezone.now(), expires_at=expires_at,
        )
        with patch("apps.sms.tasks.send_sms_task.delay") as sms:
            from apps.sms.tasks import send_expiry_reminders
            self.assertEqual(send_expiry_reminders(), 1)
        self.assertEqual(sms.call_args.args[2], "expiry_reminder")
        self.assertEqual(sms.call_args.args[3], f"reminder-{subscription.id}-{expires_at.date()}")
        self.assertIn(f"{expires_at:%b %d, %Y}", sms.call_args.args[1])

    @override_settings(USE_REDIS=False)
    def test_reminder_disabled_without_redis(self):
        from apps.sms.tasks import send_expiry_reminders
        self.assertEqual(send_expiry_reminders(), 0)


@override_settings(USE_REDIS=False, DEMO_MODE=True, DEMO_PHONE_ALLOWLIST={"2348012345678"},
                   SMS_PROVIDER="console", DEBUG=True,
                   CACHES={"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}},
                   CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class DatabaseCacheFlowTests(TestCase):
    def setUp(self):
        call_command("createcachetable", verbosity=0)
        cache.clear()

    def test_full_otp_flow_without_redis(self):
        client = APIClient()
        response = client.post("/api/auth/otp/send", {
            "phone": "08012345678", "purpose": "signup",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        verified = client.post("/api/auth/otp/verify", {
            "phone": "08012345678", "purpose": "signup", "code": response.data["code"],
            "password": "valid-password-123", "policies_accepted": True,
        }, format="json")
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(User.objects.filter(phone="+2348012345678").exists())
        self.assertEqual(SMSLog.objects.filter(purpose="otp", status=SMSLog.SENT).count(), 1)