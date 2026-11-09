import re

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import User


PHONE_PATTERN = re.compile(r"^\+234\d{10}$")


class Command(BaseCommand):
    help = "Create staff-only demo accounts for explicitly supplied Nigerian phone numbers and emails."

    def add_arguments(self, parser):
        parser.add_argument(
            "phones",
            nargs="+",
            help="Phone numbers in E.164 Nigerian format, for example +2348012345678.",
        )
        parser.add_argument(
            "--emails",
            nargs="+",
            required=True,
            help="One unique sign-in email address per phone, in the same order.",
        )

    def handle(self, *args, **options):
        phones = options["phones"]
        emails = [email.strip().lower() for email in options["emails"]]
        if any(not PHONE_PATTERN.fullmatch(phone) for phone in phones):
            raise CommandError("Every phone must be in E.164 Nigerian format: +234 followed by 10 digits.")
        if len(emails) != len(phones):
            raise CommandError("Provide exactly one email address for each phone number.")
        try:
            for email in emails:
                validate_email(email)
        except ValidationError:
            raise CommandError("Every staff account needs a valid email address.") from None
        if len(set(phones)) != len(phones):
            raise CommandError("Phone numbers must be unique.")
        if len(set(emails)) != len(emails):
            raise CommandError("Email addresses must be unique.")

        existing = {user.phone: user for user in User.objects.filter(phone__in=phones)}
        conflicts = [phone for phone, user in existing.items() if not user.is_staff]
        if conflicts:
            raise CommandError(
                "These numbers already belong to non-staff accounts; no changes were made: "
                + ", ".join(conflicts)
            )
        for phone, email in zip(phones, emails):
            if User.objects.filter(email__iexact=email).exclude(phone=phone).exists():
                raise CommandError(f"Email {email} already belongs to another account; no changes were made.")

        created = []
        already_staff = []
        with transaction.atomic():
            for phone, email in zip(phones, emails):
                user = existing.get(phone)
                if user:
                    already_staff.append(phone)
                    if user.email != email:
                        user.email = email
                        user.save(update_fields=["email"])
                    continue
                User.objects.create_user(
                    phone=phone,
                    password=None,
                    email=email,
                    is_staff=True,
                    is_superuser=False,
                    is_active=True,
                    is_phone_verified=True,
                )
                created.append(phone)

        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} staff account(s)."))
        if already_staff:
            self.stdout.write(f"Already staff: {', '.join(already_staff)}")
        self.stdout.write("Staff sign-in emails: " + ",".join(emails))