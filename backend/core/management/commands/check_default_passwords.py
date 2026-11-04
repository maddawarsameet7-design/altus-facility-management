"""
core/management/commands/check_default_passwords.py

Security audit command to detect and reject any accounts configured with
insecure default passwords (e.g. 'password123', 'altus123'). Exits non-zero if found.
The list of banned passwords is fully configurable via settings or CLI arguments.
"""
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.models import User

DEFAULT_BANNED_PASSWORDS = [
    "password123",
    "altus123",
]


class Command(BaseCommand):
    help = "Verifies that no users in the database have known default passwords (e.g. 'password123', 'altus123')."

    def add_arguments(self, parser):
        parser.add_argument(
            '--banned-passwords',
            type=str,
            default=None,
            help="Comma-separated list of banned passwords to check against."
        )

    def handle(self, *args, **options):
        cli_passwords = options.get('banned_passwords')
        if cli_passwords:
            banned_list = [p.strip() for p in cli_passwords.split(',') if p.strip()]
        else:
            settings_passwords = getattr(settings, 'BANNED_DEFAULT_PASSWORDS', None) or os.environ.get('BANNED_DEFAULT_PASSWORDS')
            if isinstance(settings_passwords, str):
                banned_list = [p.strip() for p in settings_passwords.split(',') if p.strip()]
            elif isinstance(settings_passwords, (list, tuple, set)):
                banned_list = list(settings_passwords)
            else:
                banned_list = list(DEFAULT_BANNED_PASSWORDS)

        vulnerable_findings = []
        total_checked = 0

        for user in User.objects.all():
            total_checked += 1
            for pwd in banned_list:
                if user.check_password(pwd):
                    vulnerable_findings.append((user.username, pwd))
                    break  # Found vulnerable password for this user

        if vulnerable_findings:
            details = ", ".join(f"{uname} (password: '{pwd}')" for uname, pwd in vulnerable_findings)
            msg = (
                f"SECURITY CRITICAL: Found {len(vulnerable_findings)} account(s) using "
                f"insecure default password(s): {details}.\n"
                f"All default passwords must be changed immediately before running in production."
            )
            self.stderr.write(self.style.ERROR(msg))
            raise CommandError(msg)

        banned_summary = ", ".join(f"'{p}'" for p in banned_list)
        self.stdout.write(
            self.style.SUCCESS(
                f"[PASS] Password security check PASSED: Checked {total_checked} user(s). "
                f"Zero accounts use any of the banned passwords: {banned_summary}."
            )
        )
