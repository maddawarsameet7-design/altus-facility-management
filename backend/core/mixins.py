"""
core/mixins.py — Society-aware queryset scoping for all ModelViewSets.

Drop SocietyScopedMixin into any ModelViewSet to get:
  - DIRECTOR     → unfiltered (sees all societies)
  - SUPERVISOR   → filtered to societies with active Membership
  - CHAIRMAN     → filtered to societies with active Membership
  - MEMBER       → filtered to societies with active Membership
  - WORKER       → .none() (workers use their own scoped views)

perform_create enforces that the society written to the DB is always one
the user is actually a member of. Members/Chairmen cannot override this.

get_object returns Http404 (not Http403) for cross-society access so that
society IDs cannot be probed.
"""

from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from .models import Membership, Society


def get_user_society_ids(user):
    """
    Return a queryset of Society PKs the user has an active Membership in.
    Directors have no Memberships — they access everything by role check.
    Workers never have Memberships — they access nothing via this mixin.
    """
    return Membership.objects.filter(
        user=user, is_active=True
    ).values_list('society_id', flat=True)


class SocietyScopedMixin:
    """
    Mixin for ModelViewSet subclasses that store a `society` FK.

    The host ViewSet must define `society_field` (default: 'society') pointing
    to the ForeignKey field name used in the queryset filter.

    e.g. for Attendance (which reaches society via assignment__request__society):
        society_field = 'assignment__request__society'
    """
    society_field = 'society'  # override in subclass if traversal is needed

    # ── Queryset scoping ──────────────────────────────────────────────────────

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, 'role', '')

        if role == 'DIRECTOR':
            return qs  # sees everything

        if role == 'WORKER':
            return qs.none()  # workers override entirely in their own viewset

        # MEMBER / CHAIRMAN / SUPERVISOR: scope to their active memberships
        society_ids = get_user_society_ids(user)
        return qs.filter(**{f"{self.society_field}__in": society_ids})

    # ── Object-level: 404 instead of 403 for cross-society access ────────────

    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        role = getattr(user, 'role', '')

        if role == 'DIRECTOR':
            return obj

        if role == 'WORKER':
            # Workers have their own object checks; mixin defers
            return obj

        # Retrieve the society PK from the object (supports traversal)
        field_parts = self.society_field.split('__')
        target = obj
        for part in field_parts:
            target = getattr(target, part, None)
            if target is None:
                break
        # target is now the Society instance (or None)
        society_id = getattr(target, 'pk', target)

        society_ids = list(get_user_society_ids(user))
        if society_id not in society_ids:
            raise Http404  # intentional — do not reveal existence

        return obj

    # ── perform_create: enforce society from Membership ───────────────────────

    def perform_create(self, serializer):
        user = self.request.user
        role = getattr(user, 'role', '')

        if role == 'DIRECTOR':
            # Director must supply society_id; validated in serializer
            serializer.save()
            return

        if role in ('MEMBER', 'CHAIRMAN'):
            # Auto-assign: use the user's single active Membership
            # If they have multiple (unusual), pick the most recently joined
            membership = Membership.objects.filter(
                user=user, is_active=True
            ).select_related('society').order_by('-joined_at').first()

            if not membership:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    "You are not a member of any active society. "
                    "Contact a Director or Chairman to join one."
                )
            serializer.save(society=membership.society)
            return

        if role == 'SUPERVISOR':
            # Supervisor passes society_id; must be one of their memberships
            society_id = self.request.data.get('society_id') or self.request.data.get('society')
            if not society_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    {"society_id": "Supervisors with multiple societies must specify society_id."}
                )
            society_ids = list(get_user_society_ids(user))
            if str(society_id) not in [str(s) for s in society_ids]:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You are not a supervisor of that society.")
            society = Society.objects.get(pk=society_id)
            serializer.save(society=society)
            return

        serializer.save()

