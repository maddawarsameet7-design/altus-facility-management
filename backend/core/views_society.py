"""
core/views_society.py — Society, Site, SocietySettings, Membership management,
                         and the invite/join flow.
"""
import uuid
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Society, Site, Membership, SocietySettings, InviteCode, User
from .serializers import (
    SocietySerializer, SiteSerializer, MembershipSerializer,
    SocietySettingsSerializer, InviteCodeSerializer,
)
from .permissions import IsDirectorOnly, IsOpsUser, IsSocietyChairman
from .mixins import get_user_society_ids


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _user_societies(user):
    """Return queryset of active societies the user is a member of."""
    return Society.objects.filter(
        memberships__user=user,
        memberships__is_active=True
    ).distinct()


def _user_is_chairman_of(user, society):
    return Membership.objects.filter(
        user=user, society=society, role='CHAIRMAN', is_active=True
    ).exists()


# ─── Society CRUD ─────────────────────────────────────────────────────────────

class SocietyViewSet(viewsets.ModelViewSet):
    """
    GET  /api/societies/          DIRECTOR: all; others: own societies
    POST /api/societies/          DIRECTOR only
    GET  /api/societies/{id}/     DIRECTOR: any; Chairman: own only
    PUT  /api/societies/{id}/     DIRECTOR: any; Chairman: own only
    DEL  /api/societies/{id}/     DIRECTOR only
    """
    serializer_class = SocietySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'DIRECTOR':
            return Society.objects.all()
        return _user_societies(user)

    def create(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can create societies."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        society = serializer.save()
        # Auto-create default settings
        SocietySettings.objects.get_or_create(society=society)

    def update(self, request, *args, **kwargs):
        society = self.get_object()
        if request.user.role != 'DIRECTOR' and not _user_is_chairman_of(request.user, society):
            return Response(
                {"error": "Only Directors or the Chairman can update this society."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response(
                {"error": "Only Directors can delete societies."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        if user.role == 'DIRECTOR':
            return obj
        # Non-directors: 404 if not a member
        society_ids = list(get_user_society_ids(user))
        if obj.pk not in [str(s) for s in society_ids] and obj.pk not in society_ids:
            from django.http import Http404
            raise Http404
        return obj

    # ── POST /api/societies/{id}/invite/ ──────────────────────────────────────
    @action(detail=True, methods=['post'])
    def invite(self, request, pk=None):
        """
        Create an invite code for this society.
        Allowed: Director (any society), Chairman (own society only).
        Body: { "role": "MEMBER", "max_uses": 5, "expires_at": "2026-12-31T00:00:00Z" }
        """
        society = self.get_object()
        user = request.user

        if user.role != 'DIRECTOR' and not _user_is_chairman_of(user, society):
            return Response(
                {"error": "Only Directors or the Chairman of this society can create invite codes."},
                status=status.HTTP_403_FORBIDDEN
            )

        role = request.data.get('role', 'MEMBER')
        if role not in ('MEMBER', 'CHAIRMAN', 'SUPERVISOR'):
            return Response({"error": "role must be MEMBER, CHAIRMAN, or SUPERVISOR."}, status=400)

        # Chairman can only invite MEMBERs
        if user.role != 'DIRECTOR' and role != 'MEMBER':
            return Response(
                {"error": "Chairmen can only create invite codes for MEMBER role."},
                status=status.HTTP_403_FORBIDDEN
            )

        expires_at = request.data.get('expires_at')
        max_uses = int(request.data.get('max_uses', 1))

        invite = InviteCode.objects.create(
            society=society,
            role=role,
            created_by=user,
            expires_at=expires_at,
            max_uses=max_uses,
        )
        return Response(InviteCodeSerializer(invite).data, status=status.HTTP_201_CREATED)

    # ── GET /api/societies/{id}/members/ ──────────────────────────────────────
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """List memberships. Chairman (own) + Director."""
        society = self.get_object()
        user = request.user

        if user.role != 'DIRECTOR' and not _user_is_chairman_of(user, society):
            return Response(
                {"error": "Only Directors or the Chairman can list members."},
                status=status.HTTP_403_FORBIDDEN
            )

        show_pending = request.query_params.get('pending') == 'true'
        qs = society.memberships.all()
        if show_pending:
            qs = qs.filter(is_active=False)

        serializer = MembershipSerializer(qs, many=True)
        return Response(serializer.data)

    # ── POST /api/societies/{id}/members/{user_id}/approve/ ───────────────────
    @action(detail=True, methods=['post'], url_path=r'members/(?P<user_id>[^/.]+)/approve')
    def approve_member(self, request, pk=None, user_id=None):
        """Approve a pending membership. Chairman (own) + Director."""
        society = self.get_object()
        user = request.user

        if user.role != 'DIRECTOR' and not _user_is_chairman_of(user, society):
            return Response(
                {"error": "Only Directors or the Chairman can approve members."},
                status=status.HTTP_403_FORBIDDEN
            )

        membership = get_object_or_404(Membership, society=society, user_id=user_id, is_active=False)
        membership.is_active = True
        membership.save(update_fields=['is_active'])
        return Response(MembershipSerializer(membership).data)

    # ── POST /api/societies/{id}/members/{user_id}/reject/ ────────────────────
    @action(detail=True, methods=['post'], url_path=r'members/(?P<user_id>[^/.]+)/reject')
    def reject_member(self, request, pk=None, user_id=None):
        """Reject (delete) a pending membership. Chairman (own) + Director."""
        society = self.get_object()
        user = request.user

        if user.role != 'DIRECTOR' and not _user_is_chairman_of(user, society):
            return Response(
                {"error": "Only Directors or the Chairman can reject members."},
                status=status.HTTP_403_FORBIDDEN
            )

        membership = get_object_or_404(Membership, society=society, user_id=user_id, is_active=False)
        membership.delete()
        return Response({"message": "Membership request rejected and removed."}, status=status.HTTP_200_OK)

    # ── POST /api/societies/{id}/supervisors/ ─────────────────────────────────
    @action(detail=True, methods=['post'])
    def add_supervisor(self, request, pk=None):
        """Add a Supervisor membership. Director only."""
        if request.user.role != 'DIRECTOR':
            return Response({"error": "Only Directors can assign supervisors."}, status=403)
        society = self.get_object()
        user_id = request.data.get('user_id')
        target_user = get_object_or_404(User, id=user_id)

        if target_user.role not in ('SUPERVISOR', 'DIRECTOR'):
            return Response(
                {"error": "Only users with SUPERVISOR platform role can be assigned as supervisors."},
                status=400
            )

        membership, created = Membership.objects.update_or_create(
            user=target_user, society=society,
            defaults={'role': 'SUPERVISOR', 'is_active': True}
        )
        return Response(MembershipSerializer(membership).data, status=201 if created else 200)

    # ── DELETE /api/societies/{id}/supervisors/{user_id}/ ─────────────────────
    @action(detail=True, methods=['delete'], url_path=r'supervisors/(?P<user_id>[^/.]+)')
    def remove_supervisor(self, request, pk=None, user_id=None):
        """Remove a Supervisor membership. Director only."""
        if request.user.role != 'DIRECTOR':
            return Response({"error": "Only Directors can remove supervisors."}, status=403)
        society = self.get_object()
        membership = get_object_or_404(Membership, society=society, user_id=user_id, role='SUPERVISOR')
        membership.delete()
        return Response({"message": "Supervisor removed from society."})


# ─── Join with invite code ────────────────────────────────────────────────────

class JoinSocietyView(APIView):
    """
    POST /api/societies/join/
    Body: { "code": "ALTUS-XXXXXX" }
    Any authenticated user can join with a valid code.
    Creates a Membership with is_active=False (pending Chairman approval).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        if not code:
            return Response({"error": "code is required."}, status=400)

        invite = get_object_or_404(InviteCode, code=code)

        if not invite.is_valid:
            return Response(
                {"error": "This invite code is expired, exhausted, or deactivated."},
                status=400
            )

        user = request.user
        society = invite.society

        # Prevent re-joining
        if Membership.objects.filter(user=user, society=society).exists():
            return Response(
                {"error": f"You already have a membership in {society.name}."},
                status=409
            )

        membership = Membership.objects.create(
            user=user,
            society=society,
            role=invite.role,
            is_active=False,  # pending Chairman approval
        )

        # Increment use counter
        invite.use_count += 1
        invite.save(update_fields=['use_count'])

        return Response({
            "status": "pending",
            "society": society.name,
            "role": membership.role,
            "message": f"Join request submitted to {society.name}. Waiting for Chairman approval."
        }, status=201)


# ─── Site CRUD ────────────────────────────────────────────────────────────────

class SiteViewSet(viewsets.ModelViewSet):
    """
    Sites (physical locations) within a society.
    Director: all sites.
    Supervisor/Chairman: sites in their societies.
    Member: read-only, own societies.
    """
    serializer_class = SiteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'DIRECTOR':
            return Site.objects.all()
        society_ids = get_user_society_ids(user)
        return Site.objects.filter(society__in=society_ids)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ('DIRECTOR', 'SUPERVISOR'):
            return Response({"error": "Only Directors and Supervisors can create sites."}, status=403)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if request.user.role not in ('DIRECTOR', 'SUPERVISOR'):
            return Response({"error": "Only Directors and Supervisors can update sites."}, status=403)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'DIRECTOR':
            return Response({"error": "Only Directors can delete sites."}, status=403)
        return super().destroy(request, *args, **kwargs)


# ─── SocietySettings ─────────────────────────────────────────────────────────

class SocietySettingsViewSet(viewsets.ModelViewSet):
    """
    GET/PUT /api/society-settings/{society_id}/
    Director: any society.
    Chairman: own society only.
    Others: 403.
    """
    serializer_class = SocietySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'DIRECTOR':
            return SocietySettings.objects.all()
        society_ids = get_user_society_ids(user)
        return SocietySettings.objects.filter(society__in=society_ids)

    def _check_write_permission(self, request, obj=None):
        user = request.user
        if user.role == 'DIRECTOR':
            return True
        society = obj.society if obj else None
        if society and _user_is_chairman_of(user, society):
            return True
        return False

    def update(self, request, *args, **kwargs):
        obj = self.get_object()
        if not self._check_write_permission(request, obj):
            return Response({"error": "Only Directors or the Chairman can update society settings."}, status=403)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return Response({"error": "Settings are created automatically with the society."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Society settings cannot be deleted."}, status=405)

