"""
RBAC Permission Classes for Altus Platform
============================================
Roles (defined on User.role):
  MEMBER      — Society resident. Can create/view their own service requests & pay.
  CHAIRMAN    — Society head. Same as MEMBER + can view all requests in their society.
  WORKER      — Field staff. Can view assigned jobs, clock in/out, update location.
  SUPERVISOR  — Altus ops staff. Can assign workers, update request status, view all records.
  DIRECTOR    — Platform admin. Full access: pricing, analytics, worker verification, all data.

Permission classes are composable via DRF's standard `|` and `&` operators.
"""

from rest_framework import permissions


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _role(request):
    """Safely retrieve the authenticated user's role string."""
    if request.user and request.user.is_authenticated:
        return getattr(request.user, 'role', '')
    return ''


# ─── Single-Role Guards ───────────────────────────────────────────────────────

class IsMember(permissions.BasePermission):
    """Society residents — can submit and pay for service requests."""
    message = "Access restricted to Society Members."

    def has_permission(self, request, view):
        return _role(request) == 'MEMBER'


class IsChairman(permissions.BasePermission):
    """Society chairman — elevated member with broader read access."""
    message = "Access restricted to Society Chairmen."

    def has_permission(self, request, view):
        return _role(request) == 'CHAIRMAN'


class IsWorker(permissions.BasePermission):
    """Field worker — can only access their own jobs and attendance."""
    message = "Access restricted to verified Workers."

    def has_permission(self, request, view):
        return _role(request) == 'WORKER'


class IsSupervisor(permissions.BasePermission):
    """Ops supervisor — can manage assignments and update statuses."""
    message = "Access restricted to Supervisors."

    def has_permission(self, request, view):
        return _role(request) == 'SUPERVISOR'


class IsDirector(permissions.BasePermission):
    """Platform director — full administrative access."""
    message = "Access restricted to Directors."

    def has_permission(self, request, view):
        return _role(request) == 'DIRECTOR'


# ─── Composite Guards (most commonly used) ────────────────────────────────────

class IsClientUser(permissions.BasePermission):
    """
    Members and Chairmen — the 'client side' of the platform.
    Used for: creating service requests, viewing booking history, making payments.
    """
    message = "Access restricted to Members and Chairmen."

    def has_permission(self, request, view):
        return _role(request) in ('MEMBER', 'CHAIRMAN')


class IsOpsUser(permissions.BasePermission):
    """
    Supervisors and Directors — the 'operations side' of the platform.
    Used for: worker assignment, status overrides, verification.
    """
    message = "Access restricted to Supervisors and Directors."

    def has_permission(self, request, view):
        return _role(request) in ('SUPERVISOR', 'DIRECTOR')


class IsDirectorOnly(permissions.BasePermission):
    """
    Directors only — for sensitive actions like pricing changes, platform analytics,
    and permanent user management.
    """
    message = "Access restricted to Directors."

    def has_permission(self, request, view):
        return _role(request) == 'DIRECTOR'


class IsAuthenticatedAndNotWorker(permissions.BasePermission):
    """
    Any authenticated user who is NOT a worker.
    Used for general data endpoints that workers shouldn't query freely.
    """
    message = "Workers cannot access this endpoint directly."

    def has_permission(self, request, view):
        role = _role(request)
        return bool(role) and role != 'WORKER'


# ─── Read-safe Guard (safe methods for broader roles) ─────────────────────────

class IsOpsOrReadOnly(permissions.BasePermission):
    """
    Safe (GET/HEAD/OPTIONS) methods are allowed for any authenticated user.
    Write methods are restricted to Ops (SUPERVISOR, DIRECTOR).
    """
    message = "Write access restricted to Supervisors and Directors."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return _role(request) in ('SUPERVISOR', 'DIRECTOR')


# ─── Object-Level Ownership Guards ───────────────────────────────────────────

class IsOwnerOrOps(permissions.BasePermission):
    """
    Object-level guard.
    - Ops (SUPERVISOR, DIRECTOR) always have access.
    - Others can only access objects they own.

    Ownership is determined by checking the object's `reporter`, `user`,
    or `worker.user` field against the requesting user.
    """
    message = "You do not have permission to access this object."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = _role(request)

        # Ops always wins
        if role in ('SUPERVISOR', 'DIRECTOR'):
            return True

        # Safe-method reads allowed for owners
        user = request.user

        # ServiceRequest reporter
        if hasattr(obj, 'reporter') and obj.reporter == user:
            return True

        # WorkerProfile owner
        if hasattr(obj, 'user') and obj.user == user:
            return True

        # Assignment: worker
        if hasattr(obj, 'worker') and hasattr(obj.worker, 'user') and obj.worker.user == user:
            return True

        # Attendance → assignment → worker
        if hasattr(obj, 'assignment') and hasattr(obj.assignment, 'worker'):
            if obj.assignment.worker.user == user:
                return True

        # Review: reviewer or reviewee
        if hasattr(obj, 'reviewer') and obj.reviewer == user:
            return True
        if hasattr(obj, 'reviewee') and obj.reviewee == user:
            return True

        return False


class IsWorkerSelf(permissions.BasePermission):
    """
    Object-level: allows a WORKER to access only their own WorkerProfile.
    Directors and Supervisors can always access.
    """
    message = "Workers can only access their own profile."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = _role(request)
        if role in ('SUPERVISOR', 'DIRECTOR'):
            return True
        if role == 'WORKER' and hasattr(obj, 'user'):
            return obj.user == request.user
        return False


# ─── Society-scoped Guards ────────────────────────────────────────────────────

class IsSocietyMember(permissions.BasePermission):
    """
    Object-level: user has an active Membership in obj.society.
    Used for reading a ServiceRequest, Attendance, ChatMessage.
    Returns False (caller raises Http404) if no matching Membership.

    Directors always pass. Workers are not checked here (use IsWorkerSelf).
    """
    message = "You are not a member of this society."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = _role(request)
        if role == 'DIRECTOR':
            return True
        if role == 'WORKER':
            return True  # defer to viewset-level worker checks

        # Resolve society from obj
        society = getattr(obj, 'society', None)
        if society is None:
            return False

        from .models import Membership
        return Membership.objects.filter(
            user=request.user,
            society=society,
            is_active=True
        ).exists()


class IsSocietyChairman(permissions.BasePermission):
    """
    Object-level: user has an active Membership with role=CHAIRMAN in obj.society.
    Also passes for Supervisors (of that society) and Directors.

    Used for: approving members, editing SocietySettings, creating invite codes.
    """
    message = "Only the Chairman or Director can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = _role(request)
        if role == 'DIRECTOR':
            return True

        society = getattr(obj, 'society', obj if hasattr(obj, 'memberships') else None)
        if society is None:
            return False

        from .models import Membership
        return Membership.objects.filter(
            user=request.user,
            society=society,
            role='CHAIRMAN',
            is_active=True
        ).exists()
