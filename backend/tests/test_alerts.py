from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.adminops.tasks import remind_stale_reviews
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.payments.providers.base import ProviderError, Verification
from apps.payments.services import apply_verification, initiate_payment

from .test_flow import TEST_KEY, fake_checkout, make_plans


@override_settings(ACCESS_CODE_ENC_KEY=TEST_KEY, ADMIN_ALERT_SMS=True, ADMIN_ALERT_EMAILS=["ops@example.com"])
class AlertTests(TestCase):
    def setUp(self):
        pt = patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", fake_checkout)
        pt.start(); self.addCleanup(pt.stop)
        cache.clear()
        self.monthly, _ = make_plans()
        self.cust = User.objects.create_user("+2348090000001", is_phone_verified=True)
        self.staff = User.objects.create_user("+2348090000002", email="chidi@example.com", is_staff=True)
        self.staff2 = User.objects.create_user("+2348090000003", is_staff=True)  # no email

    def mismatch(self, key="m"):
        _, p = initiate_payment(self.cust, self.monthly, "flutterwave", key)
        with self.captureOnCommitCallbacks(execute=True):
            apply_verification(p.id, Verification("SUCCESSFUL", Decimal("100"), "NGN"), "webhook")
        return p

    @patch("apps.adminops.alerts.send_sms")
    def test_review_alerts_staff_on_all_channels(self, sms):
        p = self.mismatch()
        notes = Notification.objects.filter(kind="admin_alert")
        self.assertEqual({n.user for n in notes}, {self.staff, self.staff2})
        self.assertEqual(notes.first().link, f"/admin/payments/{p.id}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(mail.outbox[0].to, ["chidi@example.com", "ops@example.com"])
        self.assertIn(f"/admin/payments/{p.id}", mail.outbox[0].body)
        self.assertEqual(sms.call_count, 2)
        self.assertFalse(Notification.objects.filter(user=self.cust, kind="admin_alert").exists())

    @patch("apps.adminops.alerts.send_sms")
    def test_no_repeat_alert_for_same_payment(self, sms):
        p = self.mismatch()
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(3):
                apply_verification(p.id, Verification("SUCCESSFUL", Decimal("100"), "NGN"), "poll")
        self.assertEqual(Notification.objects.filter(kind="admin_alert", user=self.staff).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch("apps.adminops.alerts.send_sms", side_effect=RuntimeError("sms down"))
    @patch("apps.adminops.alerts.send_mail", side_effect=RuntimeError("smtp down"))
    def test_email_and_sms_failures_do_not_break_anything(self, mail_, sms):
        p = self.mismatch()
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.NEEDS_REVIEW)
        self.assertEqual(Notification.objects.filter(kind="admin_alert").count(), 2)  # in-app still delivered

    @patch("apps.adminops.tasks.send_alert.delay", side_effect=RuntimeError("queue down"))
    def test_queue_failure_never_affects_the_payment(self, _):
        _, p = initiate_payment(self.cust, self.monthly, "flutterwave", "q")
        with self.captureOnCommitCallbacks(execute=True):
            apply_verification(p.id, Verification("SUCCESSFUL", Decimal("100"), "NGN"), "webhook")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.NEEDS_REVIEW)

    @override_settings(ADMIN_ALERT_SMS=False)
    @patch("apps.adminops.alerts.send_sms")
    def test_sms_can_be_turned_off(self, sms):
        self.mismatch()
        sms.assert_not_called()

    @patch("apps.adminops.alerts.send_sms")
    def test_works_with_no_staff(self, sms):
        User.objects.filter(is_staff=True).delete()
        p = self.mismatch("nostaff")
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.NEEDS_REVIEW)
        self.assertEqual(len(mail.outbox), 1)  # the extra ops@ address still hears about it

    @patch("apps.adminops.alerts.send_sms")
    def test_provider_failure_alerts_once(self, sms):
        with patch("apps.payments.providers.flutterwave.FlutterwaveAdapter.create_checkout", side_effect=ProviderError("x")):
            for i in range(8):
                with self.assertRaises(ProviderError):
                    initiate_payment(self.cust, self.monthly, "flutterwave", f"f{i}")
        self.assertEqual(Notification.objects.filter(kind="admin_alert", user=self.staff, title__contains="failing").count(), 1)

    @patch("apps.adminops.alerts.send_sms")
    def test_reminder_for_stale_review_once_per_window(self, sms):
        p = self.mismatch()
        mail.outbox.clear()
        self.assertEqual(remind_stale_reviews(), 0)  # too fresh
        Payment.objects.filter(pk=p.pk).update(updated_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(remind_stale_reviews(), 1)
        self.assertEqual(remind_stale_reviews(), 0)  # not again within 6 hours
        self.assertEqual(len(mail.outbox), 1)
