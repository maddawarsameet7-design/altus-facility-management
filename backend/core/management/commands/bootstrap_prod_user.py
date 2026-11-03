"""
core/management/commands/bootstrap_prod_user.py

Idempotent bootstrap command for production:
- Ensures essential service categories exist.
- Ensures a default society exists for tenant isolation.
- Ensures essential initial role accounts (DIRECTOR, CHAIRMAN, SUPERVISOR, MEMBER, WORKER)
  exist with secure production passwords (never 'password123').
"""
from django.core.management.base import BaseCommand
from core.models import User, WorkerProfile, ServiceCategory, Society, Membership


class Command(BaseCommand):
    help = 'Ensures standard service categories and essential initial users exist with secure credentials.'

    def handle(self, *args, **kwargs):
        self.stdout.write("[BOOTSTRAP] Bootstrapping production users and categories...")

        # 1. Service Categories
        categories_data = [
            ('Housekeeping', 'Deep cleaning, sanitization, and daily maintenance.', 250),
            ('Security Guard', '24/7 security patrol, access control, and monitoring.', 300),
            ('Gardening', 'Lawn mowing, landscaping, and plant care.', 200),
            ('Electrician', 'Licensed electrical repairs, wiring, and panel upgrades.', 450),
            ('Plumber', 'Pipe repair, leak fixing, and water heater installation.', 400),
        ]
        for name, desc, rate in categories_data:
            cat, created = ServiceCategory.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'base_hourly_rate': rate}
            )
            if created:
                self.stdout.write(f"  [+] Created category: {name}")

        # 2. Default Society (tenant)
        default_society, soc_created = Society.objects.get_or_create(
            name='Altus Prime Society',
            defaults={
                'client_type': 'SOCIETY',
                'address': 'Main Campus, High Street',
                'is_active': True,
            }
        )
        if soc_created:
            self.stdout.write("  [+] Created default society: Altus Prime Society")

        # 3. Essential initial users (All use secure non-default password)
        SECURE_PASS = "AltusSecure2026!"
        users_to_ensure = [
            ('admin_altus', 'director@altsan.com', 'DIRECTOR', True, True),
            ('chairman_altus', 'chairman@altsan.com', 'CHAIRMAN', False, False),
            ('supervisor_altus', 'supervisor@altsan.com', 'SUPERVISOR', False, False),
            ('member_altus', 'member@altsan.com', 'MEMBER', False, False),
            ('worker_altus', 'worker@altsan.com', 'WORKER', False, False),
        ]

        for username, email, role, is_staff, is_superuser in users_to_ensure:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'role': role,
                    'is_staff': is_staff,
                    'is_superuser': is_superuser
                }
            )
            if created:
                user.set_password(SECURE_PASS)
                user.save()
                self.stdout.write(f"  [+] Created user: {username} ({role})")

            # Worker profile
            if role == 'WORKER':
                WorkerProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'phone': '9876543210',
                        'verification_status': 'VERIFIED',
                        'average_rating': 4.8
                    }
                )

            # Society membership for tenant roles
            if role in ('MEMBER', 'CHAIRMAN', 'SUPERVISOR'):
                Membership.objects.get_or_create(
                    user=user,
                    society=default_society,
                    defaults={'role': role, 'is_active': True}
                )

        self.stdout.write("[BOOTSTRAP] Bootstrap complete.")
