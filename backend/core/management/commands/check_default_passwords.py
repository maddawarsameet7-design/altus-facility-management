"""
core/management/commands/check_default_passwords.py

Security audit command to detect and reject any accounts configured with
the insecure default password 'password123'. Exits non-zero if found.
"""
from django.core.management.base import BaseCommand, CommandError
from core.models import User

DEFAULT_VULNERABLE_PASSWORD = "password123"


class Command(BaseCommand):
    help = "Verifies that no users in the database have the default password 'password123'."

    def handle(self, *args, **options):
        vulnerable_users = []
        total_checked = 0

        for user in User.objects.all():
            total_checked += 1
            if user.check_password(DEFAULT_VULNERABLE_PASSWORD):
                vulnerable_users.append(user.username)

        if vulnerable_users:
            msg = (
                f"SECURITY CRITICAL: Found {len(vulnerable_users)} account(s) using the "
                f"insecure default password '{DEFAULT_VULNERABLE_PASSWORD}': {', '.join(vulnerable_users)}.\n"
                f"All default passwords must be changed immediately before running in production."
            )
            self.stderr.write(self.style.ERROR(msg))
            raise CommandError(msg)

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Password security check PASSED: Checked {total_checked} user(s). "
                f"Zero accounts use '{DEFAULT_VULNERABLE_PASSWORD}'."
            )
        )
