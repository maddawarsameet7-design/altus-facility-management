"""
backend/core/management/commands/decommission_worker_passwords.py

Safely decommissions legacy worker passwords by setting them unusable.
Ensures workers authenticate strictly via OTP or supervisor-issued fallback codes.

Rollout Order:
==============
Phase 1: Deploy OTP verification endpoints (/api/auth/otp/request/, /api/auth/otp/verify/).
Phase 2: Verify SMS provider delivery in production and verify field connectivity.
Phase 3: Enable supervisor fallback login code workflow (/api/workers/{id}/issue-login-code/).
Phase 4: Run dry-run audit:
         python manage.py decommission_worker_passwords --dry-run
Phase 5: Execute decommission with backup:
         python manage.py decommission_worker_passwords --backup-file backups/worker_passwords_backup.json
Phase 6: If any unexpected rollback is required:
         python manage.py decommission_worker_passwords --rollback --backup-file backups/worker_passwords_backup.json
"""

import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.models import User, AuditLog, Society


class Command(BaseCommand):
    help = "Safely and reversibly decommission worker passwords in favor of OTP/fallback login."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Audit worker password states without making changes.'
        )
        parser.add_argument(
            '--backup-file',
            type=str,
            default=None,
            help='Path to JSON file to save password hashes before deactivation or restore from on rollback.'
        )
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Restore worker passwords from a previous backup file.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        backup_file = options.get('backup_file')
        rollback = options['rollback']

        if rollback:
            if not backup_file or not os.path.exists(backup_file):
                raise CommandError("--rollback requires an existing valid --backup-file path.")
            self._execute_rollback(backup_file)
            return

        workers = User.objects.filter(role='WORKER').order_by('username')
        total_workers = workers.count()
        usable_workers = [u for u in workers if u.has_usable_password()]
        unusable_workers = total_workers - len(usable_workers)

        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(self.style.NOTICE("WORKER PASSWORD AUDIT & DECOMMISSION"))
        self.stdout.write(self.style.NOTICE("=" * 65))
        self.stdout.write(f"Total Worker accounts:        {total_workers}")
        self.stdout.write(f"Accounts with usable password: {len(usable_workers)}")
        self.stdout.write(f"Accounts already unusable:    {unusable_workers}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\n[DRY RUN COMPLETE] {len(usable_workers)} worker passwords would be set unusable. No changes made."
            ))
            return

        if not usable_workers:
            self.stdout.write(self.style.SUCCESS("All worker accounts already have unusable passwords. Nothing to do."))
            return

        # Prepare backup dictionary
        backup_data = {
            "timestamp": timezone.now().isoformat(),
            "count": len(usable_workers),
            "passwords": {u.username: u.password for u in usable_workers}
        }

        if backup_file:
            os.makedirs(os.path.dirname(os.path.abspath(backup_file)), exist_ok=True)
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Saved {len(usable_workers)} password hashes to backup file: {backup_file}"))

        default_society = Society.objects.first()
        actor = User.objects.filter(role__in=['DIRECTOR', 'SUPERVISOR']).first()
        if not actor:
            actor = User.objects.first()

        updated_count = 0

        with transaction.atomic():
            for u in usable_workers:
                u.set_unusable_password()
                u.save(update_fields=['password'])
                updated_count += 1

            if default_society and actor:
                AuditLog.objects.create(
                    society=default_society,
                    actor=actor,
                    action='DECOMMISSION_WORKER_PASSWORDS',
                    target_model='User',
                    target_id=default_society.id,
                    changes={'decommissioned_workers_count': updated_count},
                    reason='Production security policy: Enforcing OTP authentication for workers.'
                )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully decommissioned {updated_count} worker passwords. Workers now authenticate via OTP."
        ))

    def _execute_rollback(self, backup_file: str):
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        passwords = data.get('passwords', {})
        restored = 0
        with transaction.atomic():
            for username, password_hash in passwords.items():
                user = User.objects.filter(username=username, role='WORKER').first()
                if user:
                    user.password = password_hash
                    user.save(update_fields=['password'])
                    restored += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully rolled back {restored} worker passwords from {backup_file}."
        ))
