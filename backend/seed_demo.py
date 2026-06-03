import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'facility_proj.settings'

import django
django.setup()

from core.models import User, WorkerProfile, ServiceCategory, ServiceRequest

# Ensure worker has a profile
worker_user = User.objects.get(username='worker')
wp, created = WorkerProfile.objects.get_or_create(
    user=worker_user,
    defaults={
        'phone': '9876543210',
        'verification_status': 'VERIFIED',
        'average_rating': 4.5
    }
)
status_msg = "Created" if created else "Exists"
print(f"Worker profile: {status_msg}")

# Create test service requests for demo
member_user = User.objects.get(username='member')
categories = list(ServiceCategory.objects.all())

if not ServiceRequest.objects.filter(reporter=member_user).exists() and len(categories) >= 3:
    data = [
        {
            'category': categories[0],
            'location': 'Block A - Lobby',
            'issue': 'Deep cleaning required for common area before annual society event',
            'status': 'Requested',
            'priority': 'Normal'
        },
        {
            'category': categories[1],
            'location': 'Block B - Floor 3',
            'issue': 'Leaking tap in shared bathroom near stairwell, needs urgent repair',
            'status': 'Investigating',
            'priority': 'High'
        },
        {
            'category': categories[2],
            'location': 'Main Gate',
            'issue': 'Faulty wiring in corridor lights causing intermittent power cuts, safety hazard',
            'status': 'Resolved',
            'priority': 'Critical',
            'total_amount': 450.00
        },
    ]
    for d in data:
        total = d.pop('total_amount', None)
        sr = ServiceRequest.objects.create(reporter=member_user, **d)
        if total:
            sr.total_amount = total
            sr.save()
        print(f"  Created: {d['category'].name} - {d['status']}")
    print("Seeded 3 test service requests")
else:
    count = ServiceRequest.objects.filter(reporter=member_user).count()
    print(f"Requests already exist: {count}")

print("Done!")
