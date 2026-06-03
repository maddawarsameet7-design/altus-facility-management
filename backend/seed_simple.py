import os
import django
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facility_proj.settings')
django.setup()

from core.models import ServiceCategory, User

def seed():
    # Categories
    categories = [
        ('Housekeeping', 'Deep cleaning and maintenance', 250.00),
        ('Plumber', 'Plumbing and leak repairs', 400.00),
        ('Electrician', 'Certified electrical repairs', 450.00),
        ('Security Guard', 'Professional security services', 300.00),
        ('Gardening', 'Lawn and plant maintenance', 200.00),
    ]
    
    for name, desc, rate in categories:
        ServiceCategory.objects.get_or_create(
            name=name,
            defaults={'description': desc, 'base_hourly_rate': rate}
        )
        print(f"Ensured category: {name}")

    # Users
    users = [
        ('admin_altus', 'admin@altus.com', 'AdminPassword123', 'DIRECTOR'),
        ('member_test', 'member@test.com', 'password123', 'MEMBER'),
        ('worker_test', 'worker@test.com', 'password123', 'WORKER'),
    ]

    for username, email, password, role in users:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'role': role}
        )
        if created:
            user.set_password(password)
            user.save()
            print(f"Created user: {username}")
        else:
            print(f"User exists: {username}")

if __name__ == '__main__':
    seed()
