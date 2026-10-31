"""
core/tests/test_multitenancy.py
Tests covering the Society multi-tenancy layer (Steps T01–T15 from the plan).

Run with:
    cd backend
    pip install pytest-django factory-boy
    pytest core/tests/test_multitenancy.py -v
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from core.models import (
    User, Society, SocietySettings, Membership,
    ServiceRequest, ServiceCategory, InviteCode,
    ChatMessage, Attendance, Assignment, WorkerProfile,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


def make_user(username, role, password='testpass123'):
    user = User.objects.create_user(username=username, password=password, role=role)
    return user


def make_society(name='Test Society'):
    society = Society.objects.create(name=name, address='123 Test St', client_type='SOCIETY')
    SocietySettings.objects.get_or_create(society=society)
    return society


def make_membership(user, society, role='MEMBER', is_active=True):
    return Membership.objects.get_or_create(
        user=user, society=society,
        defaults={'role': role, 'is_active': is_active}
    )[0]


def make_category():
    return ServiceCategory.objects.get_or_create(name='Housekeeping')[0]


def make_service_request(reporter, society, category=None):
    if category is None:
        category = make_category()
    return ServiceRequest.objects.create(
        reporter=reporter,
        category=category,
        society=society,
        location='Block A',
        issue='Test issue',
        status='Requested',
        priority='Normal',
    )


def auth(client, user, password='testpass123'):
    response = client.post('/api/auth/login/', {'username': user.username, 'password': password}, format='json')
    assert response.status_code == 200, f"Login failed for {user.username}: {response.data}"
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


# ─── T01: Member cannot list another society's requests ───────────────────────

@pytest.mark.django_db
def test_member_cannot_see_other_society_requests(api_client):
    """Member of Society A gets empty list; Society B requests are invisible."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    member_a = make_user('member_a', 'MEMBER')
    member_b = make_user('member_b', 'MEMBER')
    make_membership(member_a, society_a)
    make_membership(member_b, society_b)

    category = make_category()
    make_service_request(member_b, society_b, category)

    auth(api_client, member_a)
    response = api_client.get('/api/requests/')
    assert response.status_code == 200
    assert response.data['count'] == 0


# ─── T02: Member retrieve of another society's request returns 404 ────────────

@pytest.mark.django_db
def test_member_retrieve_other_society_request_returns_404(api_client):
    """Direct GET on Society B's request by Society A member → 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    member_a = make_user('member_a2', 'MEMBER')
    member_b = make_user('member_b2', 'MEMBER')
    make_membership(member_a, society_a)
    make_membership(member_b, society_b)

    req_b = make_service_request(member_b, society_b)

    auth(api_client, member_a)
    response = api_client.get(f'/api/requests/{req_b.id}/')
    assert response.status_code == 404


# ─── T03: Member cannot override society on create ────────────────────────────

@pytest.mark.django_db
def test_member_cannot_set_society_to_another_on_create(api_client):
    """Member POSTs with society_id=B.id → request is created in their own society A."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    member_a = make_user('member_a3', 'MEMBER')
    make_membership(member_a, society_a)

    category = make_category()

    auth(api_client, member_a)
    response = api_client.post('/api/requests/', {
        'category_id': str(category.id),
        'society_id': str(society_b.id),  # trying to inject another society
        'location': 'Block A',
        'issue': 'Test',
        'priority': 'Normal',
    }, format='json')

    assert response.status_code == 201
    created_request = ServiceRequest.objects.get(id=response.data['id'])
    # Must be scoped to society_a, not society_b
    assert str(created_request.society_id) == str(society_a.id)


# ─── T04: Chairman only sees own society's dashboard stats ────────────────────

@pytest.mark.django_db
def test_chairman_dashboard_scoped_to_own_society(api_client):
    """Chairman A's dashboard shows only Society A's request count."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    chairman_a = make_user('chairman_a', 'CHAIRMAN')
    member_b = make_user('member_b4', 'MEMBER')
    make_membership(chairman_a, society_a, role='CHAIRMAN')
    make_membership(member_b, society_b)

    category = make_category()
    make_service_request(chairman_a, society_a, category)   # A has 1 request
    make_service_request(member_b, society_b, category)     # B has 1 request

    auth(api_client, chairman_a)
    response = api_client.get('/api/dashboard/stats/')
    assert response.status_code == 200
    # Chairman sees their own requests only (filtered by reporter=user AND society)
    assert response.data['total_requests'] == 1


# ─── T05: Chairman cannot approve member of another society ───────────────────

@pytest.mark.django_db
def test_chairman_cannot_approve_member_of_other_society(api_client):
    """Chairman A POSTing approve on Society B pending member → 403 or 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    chairman_a = make_user('chairman_a5', 'CHAIRMAN')
    applicant = make_user('applicant5', 'MEMBER')

    make_membership(chairman_a, society_a, role='CHAIRMAN')
    # Pending membership in Society B
    Membership.objects.create(user=applicant, society=society_b, role='MEMBER', is_active=False)

    auth(api_client, chairman_a)
    response = api_client.post(
        f'/api/societies/{society_b.id}/members/{applicant.id}/approve/'
    )
    # Should be 403 or 404 — Chairman A doesn't control Society B
    assert response.status_code in (403, 404)


# ─── T06: Supervisor scoped to own societies only ─────────────────────────────

@pytest.mark.django_db
def test_supervisor_scoped_to_own_societies(api_client):
    """Supervisor with memberships in A+C sees only A+C requests, not B."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')
    society_c = make_society('Society C')

    supervisor = make_user('sup6', 'SUPERVISOR')
    member_b = make_user('member_b6', 'MEMBER')
    member_a = make_user('member_a6', 'MEMBER')
    member_c = make_user('member_c6', 'MEMBER')

    make_membership(supervisor, society_a, role='SUPERVISOR')
    make_membership(supervisor, society_c, role='SUPERVISOR')
    make_membership(member_b, society_b)
    make_membership(member_a, society_a)
    make_membership(member_c, society_c)

    category = make_category()
    make_service_request(member_a, society_a, category)
    make_service_request(member_b, society_b, category)   # invisible
    make_service_request(member_c, society_c, category)

    auth(api_client, supervisor)
    response = api_client.get('/api/requests/')
    assert response.status_code == 200
    visible_ids = {str(r['id']) for r in response.data['results']}
    # Society B request must not be visible
    b_request_ids = {str(r.id) for r in ServiceRequest.objects.filter(society=society_b)}
    assert visible_ids.isdisjoint(b_request_ids)
    assert response.data['count'] == 2  # only A and C


# ─── T07: Supervisor cannot see another society's chat ────────────────────────

@pytest.mark.django_db
def test_supervisor_cannot_see_other_society_chat(api_client):
    """Chat messages for a Society B request → 404 for Supervisor of A."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    supervisor = make_user('sup7', 'SUPERVISOR')
    member_b = make_user('member_b7', 'MEMBER')
    make_membership(supervisor, society_a, role='SUPERVISOR')
    make_membership(member_b, society_b)

    req_b = make_service_request(member_b, society_b)
    ChatMessage.objects.create(request=req_b, sender=member_b, content='Hello B')

    auth(api_client, supervisor)
    response = api_client.get(f'/api/chats/?request={req_b.id}')
    assert response.status_code == 200
    # Supervisor of A should see 0 messages from Society B
    assert response.data['count'] == 0


# ─── T08: Worker only sees own attendance ─────────────────────────────────────

@pytest.mark.django_db
def test_worker_only_sees_own_attendance(api_client):
    """A worker only sees their own attendance records, not another worker's."""
    society = make_society()
    member = make_user('mem8', 'MEMBER')
    make_membership(member, society)

    worker1 = make_user('worker1_8', 'WORKER')
    worker2 = make_user('worker2_8', 'WORKER')
    wp1 = WorkerProfile.objects.create(user=worker1, phone='', verification_status='VERIFIED')
    wp2 = WorkerProfile.objects.create(user=worker2, phone='', verification_status='VERIFIED')

    category = make_category()
    req = make_service_request(member, society, category)

    assign1 = Assignment.objects.create(request=req, worker=wp1, status='ACCEPTED')
    assign2 = Assignment.objects.create(request=req, worker=wp2, status='ACCEPTED')
    Attendance.objects.create(assignment=assign1)
    Attendance.objects.create(assignment=assign2)

    auth(api_client, worker1)
    response = api_client.get('/api/attendance/my-history/')
    assert response.status_code == 200
    # Only worker1's own attendance
    assert len(response.data) == 1


# ─── T09: Director sees all societies ─────────────────────────────────────────

@pytest.mark.django_db
def test_director_sees_all(api_client):
    """Director can list service requests from all societies."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    director = make_user('director9', 'DIRECTOR')
    member_a = make_user('mem_a9', 'MEMBER')
    member_b = make_user('mem_b9', 'MEMBER')
    make_membership(member_a, society_a)
    make_membership(member_b, society_b)

    category = make_category()
    make_service_request(member_a, society_a, category)
    make_service_request(member_b, society_b, category)

    auth(api_client, director)
    response = api_client.get('/api/requests/')
    assert response.status_code == 200
    assert response.data['count'] >= 2


# ─── T10: Invite code join flow ───────────────────────────────────────────────

@pytest.mark.django_db
def test_invite_code_join_flow(api_client):
    """Director creates invite → Member joins → pending membership created."""
    director = make_user('dir10', 'DIRECTOR')
    society = make_society('Invite Society')
    new_member = make_user('newmem10', 'MEMBER')

    # Director creates invite
    auth(api_client, director)
    resp = api_client.post(f'/api/societies/{society.id}/invite/', {
        'role': 'MEMBER', 'max_uses': 5
    }, format='json')
    assert resp.status_code == 201
    code = resp.data['code']

    # New member joins
    auth(api_client, new_member)
    resp2 = api_client.post('/api/societies/join/', {'code': code}, format='json')
    assert resp2.status_code == 201
    assert resp2.data['status'] == 'pending'

    membership = Membership.objects.get(user=new_member, society=society)
    assert membership.is_active is False  # pending approval


# ─── T11: Chairman approves pending member ────────────────────────────────────

@pytest.mark.django_db
def test_chairman_approves_pending_member(api_client):
    """Chairman approves pending membership → is_active becomes True."""
    society = make_society('Approval Society')
    chairman = make_user('chair11', 'CHAIRMAN')
    applicant = make_user('applicant11', 'MEMBER')

    make_membership(chairman, society, role='CHAIRMAN')
    pending = Membership.objects.create(user=applicant, society=society, role='MEMBER', is_active=False)

    auth(api_client, chairman)
    resp = api_client.post(f'/api/societies/{society.id}/members/{applicant.id}/approve/')
    assert resp.status_code == 200

    pending.refresh_from_db()
    assert pending.is_active is True


# ─── T12: Expired invite code rejected ────────────────────────────────────────

@pytest.mark.django_db
def test_expired_invite_code_rejected(api_client):
    """Joining with an expired code → 400."""
    from django.utils import timezone
    from datetime import timedelta

    society = make_society('Expired Society')
    director = make_user('dir12', 'DIRECTOR')
    new_member = make_user('newmem12', 'MEMBER')

    invite = InviteCode.objects.create(
        society=society,
        role='MEMBER',
        created_by=director,
        max_uses=10,
        expires_at=timezone.now() - timedelta(hours=1),  # already expired
    )

    auth(api_client, new_member)
    resp = api_client.post('/api/societies/join/', {'code': invite.code}, format='json')
    assert resp.status_code == 400


# ─── T13: Invite max_uses enforced ────────────────────────────────────────────

@pytest.mark.django_db
def test_invite_max_uses_enforced(api_client):
    """Code with max_uses=1 used once, second attempt fails."""
    society = make_society('MaxUse Society')
    director = make_user('dir13', 'DIRECTOR')

    invite = InviteCode.objects.create(
        society=society, role='MEMBER', created_by=director, max_uses=1
    )

    user1 = make_user('u1_13', 'MEMBER')
    user2 = make_user('u2_13', 'MEMBER')

    auth(api_client, user1)
    resp1 = api_client.post('/api/societies/join/', {'code': invite.code}, format='json')
    assert resp1.status_code == 201

    auth(api_client, user2)
    resp2 = api_client.post('/api/societies/join/', {'code': invite.code}, format='json')
    assert resp2.status_code == 400


# ─── T14: Backfill migration assigns default society ─────────────────────────

@pytest.mark.django_db
def test_backfill_migration_membership(django_db_setup):
    """
    Verifies the backfill logic directly (not via running the migration again,
    since the DB is already migrated). We call the migration function directly.
    """
    from django.apps import apps

    society = make_society('Default Society')
    SocietySettings.objects.get_or_create(society=society)

    # Create users that should get backfilled
    user_m = make_user('bf_member', 'MEMBER')
    user_c = make_user('bf_chair', 'CHAIRMAN')
    user_s = make_user('bf_sup', 'SUPERVISOR')

    # Run the backfill function manually
    from core.migrations._0006_backfill_utils import backfill_memberships_for_society
    backfill_memberships_for_society(society, [user_m, user_c, user_s])

    assert Membership.objects.filter(user=user_m, society=society).exists()
    assert Membership.objects.filter(user=user_c, society=society, role='CHAIRMAN').exists()
    assert Membership.objects.filter(user=user_s, society=society, role='SUPERVISOR').exists()


# ─── T15: Backfill service requests ──────────────────────────────────────────

@pytest.mark.django_db
def test_backfill_service_requests():
    """ServiceRequests created without society are assigned to Default Society."""
    society = make_society('Default Society')
    member = make_user('bf_req_mem', 'MEMBER')
    make_membership(member, society)

    category = make_category()
    # Directly force society=None (simulating pre-migration state)
    req = ServiceRequest.objects.create(
        reporter=member, category=category, location='Test',
        society=None  # explicitly null
    )
    # Backfill
    ServiceRequest.objects.filter(society__isnull=True).update(society=society)
    req.refresh_from_db()
    assert req.society == society

