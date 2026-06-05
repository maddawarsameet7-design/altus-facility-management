import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import (
    User, ServiceCategory, WorkerProfile, ClientProfile,
    Property, ServiceRequest, Assignment, Review,
    PaymentTransaction, ChatMessage
)


class Command(BaseCommand):
    help = 'Seeds comprehensive demo data for the Altsan Facility Management platform'

    def handle(self, *args, **kwargs):
        self.stdout.write("🌱 Seeding Altsan demo data...")

        # ── 1. Service Categories ─────────────────────────────
        categories_data = [
            {'name': 'Housekeeping', 'description': 'Deep cleaning, sanitization, and daily maintenance of common areas and individual units.', 'rate': 250},
            {'name': 'Security Guard', 'description': 'Professional 24/7 security patrol, access control, and surveillance monitoring.', 'rate': 300},
            {'name': 'Gardening', 'description': 'Lawn mowing, landscaping, plant care, and outdoor beautification services.', 'rate': 200},
            {'name': 'Electrician', 'description': 'Licensed electrical repairs, wiring, panel upgrades, and emergency power restoration.', 'rate': 450},
            {'name': 'Plumber', 'description': 'Pipe repair, leak fixing, drain cleaning, and water heater installation.', 'rate': 400},
            {'name': 'Pest Control', 'description': 'Comprehensive pest management including termite, rodent, and insect treatment.', 'rate': 350},
            {'name': 'HVAC Technician', 'description': 'Air conditioning service, heating repair, duct cleaning, and ventilation optimization.', 'rate': 500},
            {'name': 'Carpentry', 'description': 'Furniture repair, door/window fitting, custom woodwork, and structural fixes.', 'rate': 380},
        ]

        categories = {}
        for cat in categories_data:
            obj, created = ServiceCategory.objects.get_or_create(
                name=cat['name'],
                defaults={'description': cat['description'], 'base_hourly_rate': cat['rate']}
            )
            categories[cat['name']] = obj
            status_icon = "✅" if created else "⏭️"
            self.stdout.write(f"  {status_icon} Category: {cat['name']}")

        # ── 2. Users ──────────────────────────────────────────
        password = "password123"

        users_data = [
            ('admin', 'DIRECTOR', 'admin@altsan.com', 'Priya', 'Sharma'),
            ('supervisor1', 'SUPERVISOR', 'supervisor@altsan.com', 'Rajesh', 'Verma'),
            ('chairman1', 'CHAIRMAN', 'chairman@altsan.com', 'Anita', 'Desai'),
            ('member1', 'MEMBER', 'member1@altsan.com', 'Sameet', 'Maddawar'),
            ('member2', 'MEMBER', 'member2@altsan.com', 'Vikram', 'Joshi'),
            ('member3', 'MEMBER', 'member3@altsan.com', 'Neha', 'Kapoor'),
            ('worker1', 'WORKER', 'worker1@altsan.com', 'Ramesh', 'Kumar'),
            ('worker2', 'WORKER', 'worker2@altsan.com', 'Sunil', 'Yadav'),
            ('worker3', 'WORKER', 'worker3@altsan.com', 'Deepak', 'Singh'),
            ('worker4', 'WORKER', 'worker4@altsan.com', 'Manoj', 'Gupta'),
        ]

        users = {}
        for username, role, email, first, last in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'role': role,
                    'first_name': first,
                    'last_name': last,
                }
            )
            if created:
                user.set_password(password)
                user.save()
            users[username] = user
            status_icon = "✅" if created else "⏭️"
            self.stdout.write(f"  {status_icon} User: {username} ({role})")

        # Also ensure superuser access for admin
        admin_user = users['admin']
        if not admin_user.is_superuser:
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.save()

        # ── 3. Worker Profiles ────────────────────────────────
        worker_profiles_data = [
            ('worker1', '9876543210', 'VERIFIED', 4.7, 19.0760, 72.8777),
            ('worker2', '9876543211', 'VERIFIED', 4.3, 19.0820, 72.8810),
            ('worker3', '9876543212', 'PENDING', 0.0, None, None),
            ('worker4', '9876543213', 'VERIFIED', 4.9, 19.0700, 72.8750),
        ]

        worker_profiles = {}
        for uname, phone, v_status, rating, lat, lng in worker_profiles_data:
            wp, created = WorkerProfile.objects.get_or_create(
                user=users[uname],
                defaults={
                    'phone': phone,
                    'verification_status': v_status,
                    'average_rating': rating,
                    'current_lat': lat,
                    'current_lng': lng,
                    'last_location_update': timezone.now() if lat else None,
                }
            )
            worker_profiles[uname] = wp
            status_icon = "✅" if created else "⏭️"
            self.stdout.write(f"  {status_icon} Worker Profile: {uname} ({v_status})")

        # ── 4. Client Profiles ────────────────────────────────
        client_profiles_data = [
            ('chairman1', 'Altsan Heights Residency', 'Anita Desai', '1234567890', 'SOCIETY'),
            ('member1', 'Horizon Tech Park', 'Sameet Maddawar', '9988776655', 'CORPORATE'),
        ]

        client_profiles = {}
        for uname, org, contact, phone, org_type in client_profiles_data:
            cp, created = ClientProfile.objects.get_or_create(
                user=users[uname],
                defaults={
                    'organization_name': org,
                    'contact_person': contact,
                    'phone': phone,
                    'org_type': org_type,
                }
            )
            client_profiles[uname] = cp
            status_icon = "✅" if created else "⏭️"
            self.stdout.write(f"  {status_icon} Client: {org}")

        # ── 5. Properties ────────────────────────────────────
        properties_data = [
            ('chairman1', 'Altsan Heights - Tower A', '401, Altsan Heights, Andheri West, Mumbai 400053', 19.1360, 72.8295),
            ('chairman1', 'Altsan Heights - Tower B', '402, Altsan Heights, Andheri West, Mumbai 400053', 19.1365, 72.8300),
            ('chairman1', 'Altsan Heights - Clubhouse', 'Altsan Heights Clubhouse, Andheri West, Mumbai 400053', 19.1358, 72.8290),
            ('member1', 'Horizon Tech Park - Block 1', 'Horizon Tech Park, BKC, Mumbai 400051', 19.0650, 72.8686),
            ('member1', 'Horizon Tech Park - Cafeteria', 'Horizon Tech Park Cafeteria, BKC, Mumbai 400051', 19.0655, 72.8690),
        ]

        properties = {}
        for owner_key, name, address, lat, lng in properties_data:
            prop, created = Property.objects.get_or_create(
                client=client_profiles[owner_key],
                name=name,
                defaults={'address': address, 'lat': lat, 'lng': lng}
            )
            properties[name] = prop
            status_icon = "✅" if created else "⏭️"
            self.stdout.write(f"  {status_icon} Property: {name}")

        # ── 6. Service Requests ──────────────────────────────
        now = timezone.now()
        requests_data = [
            {
                'reporter': 'member1', 'category': 'Housekeeping',
                'location': 'Tower A - Lobby',
                'issue': 'Deep cleaning required for lobby area before Diwali celebrations. Marble floors need polishing.',
                'status': 'Requested', 'priority': 'Normal',
                'created_offset_days': 0,
            },
            {
                'reporter': 'member2', 'category': 'Plumber',
                'location': 'Tower B - Floor 3, Flat 302',
                'issue': 'Severe leaking from bathroom ceiling. Water dripping into bedroom. Needs urgent repair.',
                'status': 'Investigating', 'priority': 'High',
                'created_offset_days': 1,
            },
            {
                'reporter': 'member1', 'category': 'Electrician',
                'location': 'Main Gate - Guard Room',
                'issue': 'Faulty wiring in corridor lights causing intermittent power cuts. Safety hazard for residents.',
                'status': 'In Progress', 'priority': 'Critical',
                'total_amount': Decimal('2250.00'),
                'created_offset_days': 3,
            },
            {
                'reporter': 'member3', 'category': 'Security Guard',
                'location': 'Altsan Heights - Main Entrance',
                'issue': 'Need additional night security guard for parking area. Recent theft incidents reported.',
                'status': 'Requested', 'priority': 'High',
                'created_offset_days': 0,
            },
            {
                'reporter': 'member2', 'category': 'Gardening',
                'location': 'Clubhouse - Rear Garden',
                'issue': 'Overgrown hedges blocking pathway. Lawn needs mowing before society annual meet.',
                'status': 'Resolved', 'priority': 'Normal',
                'total_amount': Decimal('800.00'),
                'created_offset_days': 10,
            },
            {
                'reporter': 'chairman1', 'category': 'Pest Control',
                'location': 'Tower A - Basement Parking',
                'issue': 'Cockroach and rodent infestation in basement parking area. All residents complaining.',
                'status': 'In Progress', 'priority': 'Critical',
                'total_amount': Decimal('3500.00'),
                'created_offset_days': 2,
            },
            {
                'reporter': 'member1', 'category': 'HVAC Technician',
                'location': 'Horizon Tech Park - Block 1, Floor 5',
                'issue': 'Central AC unit making loud noise and not cooling effectively. Temperature reaching 30°C indoors.',
                'status': 'Investigating', 'priority': 'Medium',
                'created_offset_days': 1,
            },
            {
                'reporter': 'member3', 'category': 'Carpentry',
                'location': 'Tower B - Community Hall',
                'issue': 'Broken door hinges on community hall entrance. Door cannot close properly, security concern.',
                'status': 'Resolved', 'priority': 'Medium',
                'total_amount': Decimal('1200.00'),
                'created_offset_days': 15,
            },
            {
                'reporter': 'member2', 'category': 'Housekeeping',
                'location': 'Tower A - Swimming Pool Area',
                'issue': 'Swimming pool area needs deep sanitization. Tiles are slippery and changing rooms need cleaning.',
                'status': 'Requested', 'priority': 'Normal',
                'created_offset_days': 0,
            },
            {
                'reporter': 'chairman1', 'category': 'Electrician',
                'location': 'Altsan Heights - Generator Room',
                'issue': 'Backup generator failing to start during power cuts. Need full inspection and servicing.',
                'status': 'Requested', 'priority': 'Critical',
                'created_offset_days': 0,
            },
        ]

        service_requests = []
        if ServiceRequest.objects.count() < 3:
            for req_data in requests_data:
                sr = ServiceRequest.objects.create(
                    reporter=users[req_data['reporter']],
                    category=categories[req_data['category']],
                    location=req_data['location'],
                    issue=req_data['issue'],
                    status=req_data['status'],
                    priority=req_data['priority'],
                    total_amount=req_data.get('total_amount'),
                )
                # Backdate the created_at
                offset = req_data.get('created_offset_days', 0)
                if offset:
                    ServiceRequest.objects.filter(pk=sr.pk).update(
                        created_at=now - timedelta(days=offset)
                    )
                service_requests.append(sr)
                self.stdout.write(f"  ✅ Request: {req_data['category']} at {req_data['location']} ({req_data['status']})")
        else:
            service_requests = list(ServiceRequest.objects.all()[:10])
            self.stdout.write(f"  ⏭️ Service requests already exist ({ServiceRequest.objects.count()} total)")

        # ── 7. Assignments ───────────────────────────────────
        # Assign workers to in-progress / investigating requests
        if Assignment.objects.count() == 0 and len(service_requests) >= 6:
            assignments_data = [
                (service_requests[1], 'worker2', 'ACCEPTED'),     # Plumber investigating
                (service_requests[2], 'worker1', 'ACCEPTED'),     # Electrician in progress
                (service_requests[4], 'worker1', 'COMPLETED'),    # Gardening resolved
                (service_requests[5], 'worker4', 'ACCEPTED'),     # Pest control in progress
                (service_requests[7], 'worker4', 'COMPLETED'),    # Carpentry resolved
            ]
            for sr, worker_key, a_status in assignments_data:
                Assignment.objects.create(
                    request=sr,
                    worker=worker_profiles[worker_key],
                    status=a_status,
                )
                self.stdout.write(f"  ✅ Assignment: {worker_key} → {sr.category.name} ({a_status})")
        else:
            self.stdout.write(f"  ⏭️ Assignments already exist ({Assignment.objects.count()} total)")

        # ── 8. Reviews (for resolved requests) ───────────────
        if Review.objects.count() == 0 and len(service_requests) >= 8:
            reviews_data = [
                (service_requests[4], 'member2', 'worker1', 5, 'Excellent work! Garden looks beautiful now. Very professional.'),
                (service_requests[7], 'member3', 'worker4', 4, 'Fixed the door quickly. Good quality work, slightly expensive.'),
                (service_requests[4], 'worker1', 'member2', 5, 'Very cooperative resident. Clear instructions provided.'),
            ]
            for sr, reviewer_key, reviewee_key, rating, comment in reviews_data:
                Review.objects.create(
                    request=sr,
                    reviewer=users[reviewer_key],
                    reviewee=users[reviewee_key],
                    rating=rating,
                    comment=comment,
                )
                self.stdout.write(f"  ✅ Review: {reviewer_key} → {reviewee_key} ({rating}⭐)")
        else:
            self.stdout.write(f"  ⏭️ Reviews already exist ({Review.objects.count()} total)")

        # ── 9. Payment Transactions (for resolved requests) ──
        if PaymentTransaction.objects.count() == 0 and len(service_requests) >= 8:
            payments_data = [
                (service_requests[4], Decimal('800.00'), 'SUCCESS'),
                (service_requests[7], Decimal('1200.00'), 'SUCCESS'),
            ]
            for sr, amount, p_status in payments_data:
                PaymentTransaction.objects.create(
                    request=sr,
                    transaction_id=f"TX-{uuid.uuid4().hex[:8].upper()}",
                    amount=amount,
                    status=p_status,
                )
                sr.is_paid = True
                sr.save()
                self.stdout.write(f"  ✅ Payment: ₹{amount} for {sr.category.name} ({p_status})")
        else:
            self.stdout.write(f"  ⏭️ Payments already exist ({PaymentTransaction.objects.count()} total)")

        # ── 10. Chat Messages ────────────────────────────────
        if ChatMessage.objects.count() == 0 and len(service_requests) >= 6:
            chats_data = [
                (service_requests[1], 'member2', 'Hi, the leak is getting worse. Can someone come ASAP?'),
                (service_requests[1], 'worker2', 'On my way! Will be there in 30 minutes.'),
                (service_requests[1], 'member2', 'Thank you! Please ring flat 302 when you arrive.'),
                (service_requests[2], 'member1', 'The lights in corridor B are flickering badly.'),
                (service_requests[2], 'worker1', 'Checked the wiring — old insulation needs replacement. Will take 2 hours.'),
                (service_requests[5], 'chairman1', 'This is urgent. Multiple families are affected.'),
                (service_requests[5], 'worker4', 'Starting treatment in basement area. Will cover all levels by tomorrow.'),
            ]
            for sr, sender_key, content in chats_data:
                ChatMessage.objects.create(
                    request=sr,
                    sender=users[sender_key],
                    content=content,
                )
            self.stdout.write(f"  ✅ Chat messages: {len(chats_data)} messages seeded")
        else:
            self.stdout.write(f"  ⏭️ Chat messages already exist ({ChatMessage.objects.count()} total)")

        # ── Summary ──────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("═" * 50))
        self.stdout.write(self.style.SUCCESS("  🎉 Altsan demo data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS("═" * 50))
        self.stdout.write(f"  Categories:    {ServiceCategory.objects.count()}")
        self.stdout.write(f"  Users:         {User.objects.count()}")
        self.stdout.write(f"  Workers:       {WorkerProfile.objects.count()}")
        self.stdout.write(f"  Clients:       {ClientProfile.objects.count()}")
        self.stdout.write(f"  Properties:    {Property.objects.count()}")
        self.stdout.write(f"  Requests:      {ServiceRequest.objects.count()}")
        self.stdout.write(f"  Assignments:   {Assignment.objects.count()}")
        self.stdout.write(f"  Reviews:       {Review.objects.count()}")
        self.stdout.write(f"  Payments:      {PaymentTransaction.objects.count()}")
        self.stdout.write(f"  Chat Messages: {ChatMessage.objects.count()}")
        self.stdout.write("")
        self.stdout.write("  🔑 Login credentials:")
        self.stdout.write("     Admin:      admin / password123")
        self.stdout.write("     Supervisor: supervisor1 / password123")
        self.stdout.write("     Chairman:   chairman1 / password123")
        self.stdout.write("     Member:     member1 / password123")
        self.stdout.write("     Worker:     worker1 / password123")
        self.stdout.write("")
