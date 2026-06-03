import uuid
from django.core.management.base import BaseCommand
from core.models import User, ServiceCategory, WorkerProfile, ClientProfile
from django.utils import timezone

class Command(BaseCommand):
    help = 'Seeds initial data for the Altus Facility Management platform'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding data...")

        # 1. Create Service Categories
        categories_data = [
            {'name': 'Housekeeping', 'description': 'Deep cleaning and maintenance', 'rate': 250},
            {'name': 'Security Guard', 'description': 'Professional security services', 'rate': 300},
            {'name': 'Gardening', 'description': 'Lawn and plant maintenance', 'rate': 200},
            {'name': 'Electrician', 'description': 'Certified electrical repairs', 'rate': 450},
            {'name': 'Plumber', 'description': 'Plumbing and leak repairs', 'rate': 400},
        ]

        categories = {}
        for cat in categories_data:
            obj, created = ServiceCategory.objects.get_or_create(
                name=cat['name'],
                defaults={'description': cat['description'], 'base_hourly_rate': cat['rate']}
            )
            categories[cat['name']] = obj
            self.stdout.write(f"Category {cat['name']} created.")

        # 2. Create Test Users
        roles = [
            ('director', 'DIRECTOR', 'director@altus.com'),
            ('supervisor', 'SUPERVISOR', 'supervisor@altus.com'),
            ('worker', 'WORKER', 'worker@altus.com'),
            ('chairman', 'CHAIRMAN', 'chairman@altus.com'),
            ('member', 'MEMBER', 'member@altus.com'),
        ]

        password = "password123"
        users = {}
        for username, role, email in roles:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'role': role,
                    'first_name': username.capitalize(),
                    'last_name': 'Altus'
                }
            )
            user.set_password(password)
            user.save()
            users[role] = user
            self.stdout.write(f"User {username} ({role}) created.")

        # 3. Create Profiles
        # Worker Profile
        WorkerProfile.objects.get_or_create(
            user=users['WORKER'],
            defaults={'phone': '9876543210', 'verification_status': 'VERIFIED'}
        )

        # Client Profile (The Society)
        ClientProfile.objects.get_or_create(
            user=users['CHAIRMAN'],
            defaults={
                'organization_name': 'Altus Heights Residency',
                'contact_person': 'Chairman Altus',
                'phone': '1234567890',
                'org_type': 'SOCIETY'
            }
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded Altus data.'))
