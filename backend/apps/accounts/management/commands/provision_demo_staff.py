import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User


PHONE_PATTERN = re.compile(r"^\+234\d{10}$")


class Command(BaseCommand):
    help = "Create staff-only demo accounts for explicitly supplied Nigerian phone numbers."

    def add_arguments(self, parser):
        parser.add_argument(
            "phones",
            nargs="+",
            help="Phone numbers in E.164 Nigerian format, for example +2348012345678.",
        )

    def handle(self, *args, **options):
        phones = options["phones"]
        if any(not PHONE_PATTERN.fullmatch(phone) for phone in phones):
            raise CommandError("Every phone must be in E.164 Nigerian format: +234 followed by 10 digits.")
        if len(set(phones)) != len(phones):
            raise CommandError("Phone numbers must be unique.")

        existing = {user.phone: user for user in User.objects.filter(phone__in=phones)}
        conflicts = [phone for phone, user in existing.items() if not user.is_staff]
        if conflicts:
            raise CommandError(
                "These numbers already belong to non-staff accounts; no changes were made: "
                + ", ".join(conflicts)
            )

        created = []
        already_staff = []
        with transaction.atomic():
            for phone in phones:
                user = existing.get(phone)
                if user:
                    already_staff.append(phone)
                    continue
                User.objects.create_user(
                    phone=phone,
                    password=None,
                    is_staff=True,
                    is_superuser=False,
                    is_active=True,
                    is_phone_verified=True,
                )
                created.append(phone)

        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} staff account(s)."))
        if already_staff:
            self.stdout.write(f"Already staff: {', '.join(already_staff)}")
        self.stdout.write("Set DEMO_PHONE_ALLOWLIST in Render to:")
        self.stdout.write(",".join(phones))