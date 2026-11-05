from io import StringIO

from django.core.management import call_command, CommandError
from django.test import TestCase

from apps.accounts.models import User


class ProvisionDemoStaffCommandTests(TestCase):
    def test_creates_staff_only_accounts_and_is_idempotent(self):
        phones = ["+2348012345678", "+2348033261870"]
        output = StringIO()

        call_command("provision_demo_staff", *phones, stdout=output)

        users = list(User.objects.filter(phone__in=phones).order_by("phone"))
        self.assertEqual(len(users), 2)
        for user in users:
            self.assertTrue(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertTrue(user.is_active)
            self.assertTrue(user.is_phone_verified)
            self.assertTrue(user.has_usable_password() is False)
        self.assertIn(",".join(phones), output.getvalue())

        call_command("provision_demo_staff", *phones, stdout=StringIO())
        self.assertEqual(User.objects.filter(phone__in=phones).count(), 2)

    def test_existing_customer_prevents_all_changes(self):
        customer = User.objects.create_user("+2348012345678", "customer-password")

        with self.assertRaisesRegex(CommandError, "no changes were made"):
            call_command("provision_demo_staff", "+2348033261870", customer.phone)

        self.assertFalse(User.objects.filter(phone="+2348033261870").exists())
        customer.refresh_from_db()
        self.assertFalse(customer.is_staff)

    def test_rejects_non_nigerian_or_malformed_phone(self):
        with self.assertRaises(CommandError):
            call_command("provision_demo_staff", "08012345678")

    def test_rejects_duplicate_numbers(self):
        with self.assertRaisesRegex(CommandError, "must be unique"):
            call_command("provision_demo_staff", "+2348012345678", "+2348012345678")