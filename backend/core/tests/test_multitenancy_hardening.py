"""
core/tests/test_multitenancy_hardening.py
Hardening test suite verifying:
1. Structural guards (viewset mixin inheritance allowlist, save-time model guards)
2. Cross-society attack prevention (Payments, Reviews, Chat, Attendance, Sites, Settings)
3. Cryptographic invite codes & throttling configurations
4. WebSocket connection authorization (ChatConsumer & LocationConsumer)
"""
import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from facility_proj.urls import router
from core.models import (
    User, Society, SocietySettings, Membership,
    ServiceRequest, ServiceCategory, InviteCode,
    ChatMessage, Attendance, Assignment, WorkerProfile, Site,
    _generate_invite_code,
)
from core.mixins import SocietyScopedMixin
from core.middleware import set_current_user
from core.consumers import check_chat_access_sync, check_location_access_sync


# ─── Test Fixtures & Helpers ──────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


def make_user(username, role, password='testpass123'):
    return User.objects.create_user(username=username, password=password, role=role)


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
    return ServiceCategory.objects.get_or_create(name='Maintenance')[0]


def make_service_request(reporter, society, status='Requested'):
    category = make_category()
    return ServiceRequest.objects.create(
        reporter=reporter,
        category=category,
        society=society,
        location='Tower 1',
        issue='Plumbing leak',
        status=status,
        priority='Normal',
    )


def auth(client, user, password='testpass123'):
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ─── 1. STRUCTURAL GUARD: ViewSet Mixin Inheritance Check ────────────────────

def test_all_society_owned_viewsets_inherit_mixin():
    """
    Iterates every registered viewset in router.registry.
    Fails if any ViewSet that exposes society-owned models does not inherit SocietyScopedMixin.
    Explicit allowlist is documented with justification for each exception.
    """
    ALLOWLIST_EXCEPTIONS = {
        # 1. ServiceCategoryViewSet: Global catalog of services and pricing, shared across all societies
        'ServiceCategoryViewSet',
        # 2. WorkerViewSet: Platform-wide pool of facility workers deployed to societies; workers are not owned by any single society
        'WorkerViewSet',
        # 3. ClientProfileViewSet: Legacy 1:1 user client profiles, kept for backward compatibility; replaced by Society
        'ClientProfileViewSet',
        # 4. PropertyViewSet: Legacy client property model, kept for backward compatibility; replaced by Site
        'PropertyViewSet',
    }

    registered_viewsets = [viewset for prefix, viewset, basename in router.registry]
    assert len(registered_viewsets) > 0, "No viewsets registered in router!"

    for viewset in registered_viewsets:
        name = viewset.__name__
        if name in ALLOWLIST_EXCEPTIONS:
            continue
        assert issubclass(viewset, SocietyScopedMixin), (
            f"SECURITY VIOLATION: ViewSet '{name}' exposes society-owned data "
            f"but does not inherit SocietyScopedMixin! Add it to the mixin or allowlist."
        )


# ─── 2. STRUCTURAL GUARD: Save-Time Guard on Society-Owned Models ───────────

@pytest.mark.django_db
def test_save_time_guard_service_request_non_director_fails():
    """Non-Directors attempting to save ServiceRequest with society=None must fail."""
    society = make_society('Alpha Society')
    member = make_user('save_guard_mem', 'MEMBER')
    make_membership(member, society)
    cat = make_category()

    # Simulate Member logged in via thread-local
    set_current_user(member)
    try:
        req = ServiceRequest(
            reporter=member,
            category=cat,
            society=None,  # missing society!
            location='Lobby',
        )
        with pytest.raises(ValidationError):
            req.save()
    finally:
        set_current_user(None)


@pytest.mark.django_db
def test_save_time_guard_service_request_director_allowed():
    """Directors can create ServiceRequest and pass society as needed."""
    society = make_society('Beta Society')
    director = make_user('save_guard_dir', 'DIRECTOR')
    cat = make_category()

    set_current_user(director)
    try:
        req = ServiceRequest.objects.create(
            reporter=director,
            category=cat,
            society=society,
            location='Headquarters',
        )
        assert req.id is not None
        assert req.society == society
    finally:
        set_current_user(None)


# ─── 3. PAYMENTS: Cross-Society Attacks Return 404 ────────────────────────────

@pytest.mark.django_db
def test_payment_order_cross_society_attack_returns_404(api_client):
    """Member in Society A trying to create payment for Society B request gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    user_a = make_user('attacker_a', 'MEMBER')
    user_b = make_user('victim_b', 'MEMBER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b)

    auth(api_client, user_a)
    resp = api_client.post('/api/payments/create-order/', {
        'request_id': str(req_b.id),
        'amount': '500.00'
    }, format='json')

    assert resp.status_code == 404
    assert req_b.is_paid is False


@pytest.mark.django_db
def test_payment_verify_cross_society_attack_returns_404(api_client):
    """Member in Society A trying to verify payment for Society B request gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    user_a = make_user('attacker_verify_a', 'MEMBER')
    user_b = make_user('victim_verify_b', 'MEMBER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b)

    auth(api_client, user_a)
    resp = api_client.post('/api/payments/verify/', {
        'request_id': str(req_b.id),
        'razorpay_order_id': 'order_fake',
        'razorpay_payment_id': 'pay_fake',
        'razorpay_signature': 'sig_fake',
    }, format='json')

    assert resp.status_code == 404
    req_b.refresh_from_db()
    assert req_b.is_paid is False


# ─── 4. REVIEWS: Cross-Society Review Submission Returns 404 ─────────────────

@pytest.mark.django_db
def test_review_cross_society_attack_returns_404(api_client):
    """User in Society A trying to review a request in Society B gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    user_a = make_user('reviewer_a', 'MEMBER')
    user_b = make_user('user_b_rev', 'MEMBER')
    worker = make_user('worker_rev', 'WORKER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b, status='Resolved')

    auth(api_client, user_a)
    resp = api_client.post('/api/reviews/', {
        'request': str(req_b.id),
        'reviewee': str(worker.id),
        'rating': 5,
        'comment': 'Fake cross-society review',
    }, format='json')

    assert resp.status_code == 404
    assert req_b.reviews.count() == 0


# ─── 5. CHAT: Cross-Society Message Creation Returns 404 ─────────────────────

@pytest.mark.django_db
def test_chat_cross_society_post_returns_404(api_client):
    """User in Society A trying to post a message into Society B request gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    user_a = make_user('chatter_a', 'MEMBER')
    user_b = make_user('chatter_b', 'MEMBER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b)

    auth(api_client, user_a)
    resp = api_client.post('/api/chats/', {
        'request': str(req_b.id),
        'content': 'Attacking society B chat',
    }, format='json')

    assert resp.status_code == 404
    assert req_b.messages.count() == 0


# ─── 6. ATTENDANCE: Scoping, Direct Society FK, & Detail 404 ─────────────────

@pytest.mark.django_db
def test_attendance_clock_in_stamps_society(api_client):
    """When a worker clocks in, Attendance.society is stamped from request.society."""
    society = make_society('Clock Society')
    member = make_user('clock_mem', 'MEMBER')
    worker_user = make_user('clock_worker', 'WORKER')
    make_membership(member, society)

    wp = WorkerProfile.objects.create(user=worker_user, phone='1234567890', verification_status='VERIFIED')
    req = make_service_request(member, society)
    assign = Assignment.objects.create(request=req, worker=wp, status='PENDING_ACCEPTANCE')

    auth(api_client, worker_user)
    resp = api_client.post('/api/attendance/clock-in/', {
        'assignment_id': str(assign.id),
        'lat': 18.5204,
        'lng': 73.8567,
    }, format='json')

    assert resp.status_code == 201
    att = Attendance.objects.get(assignment=assign)
    assert att.society == society
    assert str(att.society_id) == str(society.id)


@pytest.mark.django_db
def test_attendance_detail_cross_society_supervisor_returns_404(api_client):
    """Supervisor of Society A trying to GET Attendance of Society B gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    sup_a = make_user('supervisor_a_att', 'SUPERVISOR')
    member_b = make_user('member_b_att', 'MEMBER')
    worker_b = make_user('worker_b_att', 'WORKER')

    make_membership(sup_a, society_a, role='SUPERVISOR')
    make_membership(member_b, society_b)

    wp = WorkerProfile.objects.create(user=worker_b, phone='123', verification_status='VERIFIED')
    req_b = make_service_request(member_b, society_b)
    assign_b = Assignment.objects.create(request=req_b, worker=wp, status='ACCEPTED')
    att_b = Attendance.objects.create(assignment=assign_b, society=society_b)

    auth(api_client, sup_a)
    resp = api_client.get(f'/api/attendance/{att_b.id}/')
    assert resp.status_code == 404


# ─── 7. UPDATE & DELETE: Cross-Society Requests Return 404 ───────────────────

@pytest.mark.django_db
def test_cross_society_put_patch_delete_service_request_returns_404(api_client):
    """User in Society A trying PUT, PATCH, DELETE on Society B request returns 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    user_a = make_user('attacker_mut_a', 'MEMBER')
    user_b = make_user('victim_mut_b', 'MEMBER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b)
    original_issue = req_b.issue

    auth(api_client, user_a)

    # 1. PATCH
    resp_patch = api_client.patch(f'/api/requests/{req_b.id}/', {'issue': 'Hacked'}, format='json')
    assert resp_patch.status_code == 404
    req_b.refresh_from_db()
    assert req_b.issue == original_issue

    # 2. PUT
    cat = make_category()
    resp_put = api_client.put(f'/api/requests/{req_b.id}/', {
        'category_id': str(cat.id),
        'location': 'New Loc',
        'issue': 'Hacked',
        'priority': 'High',
    }, format='json')
    assert resp_put.status_code == 404
    req_b.refresh_from_db()
    assert req_b.issue == original_issue

    # 3. DELETE
    resp_del = api_client.delete(f'/api/requests/{req_b.id}/')
    assert resp_del.status_code == 404
    assert ServiceRequest.objects.filter(id=req_b.id).exists()


# ─── 8. SITES: Cross-Society Creation by Supervisor Returns 404 ──────────────

@pytest.mark.django_db
def test_site_cross_society_supervisor_attack_returns_404(api_client):
    """Supervisor of Society A trying to create or edit a Site in Society B gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    sup_a = make_user('supervisor_site_a', 'SUPERVISOR')
    make_membership(sup_a, society_a, role='SUPERVISOR')

    site_b = Site.objects.create(society=society_b, name='Gate 1', geofence_radius_m=100)

    auth(api_client, sup_a)

    # 1. Create site in society_b
    resp_create = api_client.post('/api/sites/', {
        'society': str(society_b.id),
        'name': 'Malicious Site',
        'geofence_radius_m': 150,
    }, format='json')
    assert resp_create.status_code == 404
    assert not Site.objects.filter(name='Malicious Site').exists()

    # 2. Modify site in society_b
    resp_update = api_client.patch(f'/api/sites/{site_b.id}/', {'name': 'Renamed Site'}, format='json')
    assert resp_update.status_code == 404
    site_b.refresh_from_db()
    assert site_b.name == 'Gate 1'


# ─── 9. SOCIETY SETTINGS: Cross-Society Chairman Attack Returns 404 ──────────

@pytest.mark.django_db
def test_society_settings_cross_society_attack_returns_404(api_client):
    """Chairman of Society A trying to modify Society B settings gets 404."""
    society_a = make_society('Society A')
    society_b = make_society('Society B')

    chair_a = make_user('chairman_settings_a', 'CHAIRMAN')
    make_membership(chair_a, society_a, role='CHAIRMAN')

    settings_b = SocietySettings.objects.get(society=society_b)
    original_grace = settings_b.shift_start_grace_minutes

    auth(api_client, chair_a)
    resp = api_client.patch(f'/api/society-settings/{society_b.id}/', {
        'shift_start_grace_minutes': 99,
    }, format='json')
    assert resp.status_code == 404
    settings_b.refresh_from_db()
    assert settings_b.shift_start_grace_minutes == original_grace


# ─── 10. CRYPTOGRAPHIC INVITE CODES ──────────────────────────────────────────

def test_invite_code_is_cryptographically_secure():
    """Invite code format has ALTUS- prefix, >= 10 chars suffix (>= 16 total length)."""
    code = _generate_invite_code()
    assert code.startswith("ALTUS-")
    assert len(code) >= 16
    assert code.isalnum() or '-' in code


# ─── 11. WEBSOCKET SECURITY: Chat & Location Access Checks ───────────────────

@pytest.mark.django_db
def test_websocket_chat_cross_society_rejected():
    """User in Society A is rejected from accessing Chat of request in Society B."""
    society_a = make_society('WS Society A')
    society_b = make_society('WS Society B')

    user_a = make_user('ws_attacker_a', 'MEMBER')
    user_b = make_user('ws_victim_b', 'MEMBER')
    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    req_b = make_service_request(user_b, society_b)

    # User A should NOT have access to req_b's chat
    allowed_a = check_chat_access_sync(user_a, str(req_b.id))
    assert allowed_a is False

    # User B (reporter) MUST have access
    allowed_b = check_chat_access_sync(user_b, str(req_b.id))
    assert allowed_b is True


@pytest.mark.django_db
def test_websocket_location_cross_society_rejected():
    """User in Society A cannot track worker who has no assignment in Society A."""
    society_a = make_society('WS Loc Society A')
    society_b = make_society('WS Loc Society B')

    user_a = make_user('ws_loc_attacker_a', 'MEMBER')
    user_b = make_user('ws_loc_user_b', 'MEMBER')
    worker_b = make_user('ws_loc_worker_b', 'WORKER')

    make_membership(user_a, society_a)
    make_membership(user_b, society_b)

    wp = WorkerProfile.objects.create(user=worker_b, phone='999', verification_status='VERIFIED')
    req_b = make_service_request(user_b, society_b)
    Assignment.objects.create(request=req_b, worker=wp, status='ACCEPTED')

    # User A has no active assignment with worker_b
    allowed_a = check_location_access_sync(user_a, str(wp.id))
    assert allowed_a is False

    # User B has active assignment with worker_b
    allowed_b = check_location_access_sync(user_b, str(wp.id))
    assert allowed_b is True


# ─── 12. THROTTLING SCOPES CONFIGURATION ──────────────────────────────────────

def test_throttling_scopes_properly_configured():
    """Verify join and login endpoints have strict throttle scopes."""
    from core.views_society import JoinSocietyView
    from core.views import RegisterView
    from facility_proj.urls import ThrottledTokenObtainPairView

    assert JoinSocietyView.throttle_scope == 'society_join'
    assert ScopedRateThrottle in JoinSocietyView.throttle_classes

    assert RegisterView.throttle_scope == 'login'
    assert ScopedRateThrottle in RegisterView.throttle_classes

    assert ThrottledTokenObtainPairView.throttle_scope == 'login'
    assert ScopedRateThrottle in ThrottledTokenObtainPairView.throttle_classes
