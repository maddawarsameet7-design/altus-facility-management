"""
core/mixins.py — Society-aware queryset scoping for all ModelViewSets.

Drop SocietyScopedMixin into any ModelViewSet to get:
  - DIRECTOR     → unfiltered (sees all societies)
  - SUPERVISOR   → filtered to societies with active Membership
  - CHAIRMAN     → filtered to societies with active Membership
  - MEMBER       → filtered to societies with active Membership
  - WORKER       → .none() (or worker self-records when overridden)

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
    if not user or not user.is_authenticated:
        return Membership.objects.none().values_list('society_id', flat=True)
    return Membership.objects.filter(
        user=user, is_active=True
    ).values_list('society_id', flat=True)


class SocietyScopedMixin:
    """
    Mixin for ModelViewSet subclasses that store a `society` FK or self-reference.

    The host ViewSet must define `society_field` (default: 'society') pointing
    to the ForeignKey field name used in the queryset filter.
    """
    society_field = 'society'

    # ── Queryset scoping ──────────────────────────────────────────────────────

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        role = getattr(user, 'role', '')

        if role == 'DIRECTOR':
            return qs

        if role == 'WORKER':
            return qs.none()

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
            return obj

        # Retrieve the society PK from the object (supports traversal)
        field_parts = self.society_field.split('__')
        target = obj
        for part in field_parts:
            target = getattr(target, part, None)
            if target is None:
                break
        society_id = getattr(target, 'pk', target)

        society_ids = [str(s) for s in get_user_society_ids(user)]
        if str(society_id) not in society_ids:
            raise Http404

        return obj

    # ── perform_create: enforce society from Membership ───────────────────────

    def resolve_create_society(self, request):
        """Helper to resolve and validate the appropriate society for object creation."""
        user = request.user
        role = getattr(user, 'role', '')

        if role == 'DIRECTOR':
            society_id = request.data.get('society_id') or request.data.get('society')
            if society_id:
                try:
                    return Society.objects.get(pk=society_id)
                except Society.DoesNotExist:
                    raise Http404
            return None

        if role in ('MEMBER', 'CHAIRMAN'):
            membership = Membership.objects.filter(
                user=user, is_active=True
            ).select_related('society').order_by('-joined_at').first()

            if not membership:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    "You are not a member of any active society. "
                    "Contact a Director or Chairman to join one."
                )
            return membership.society

        if role == 'SUPERVISOR':
            society_id = request.data.get('society_id') or request.data.get('society')
            if not society_id:
                from rest_framework.exceptions import ValidationError
                raise ValidationError(
                    {"society_id": "Supervisors must specify society_id."}
                )
            society_ids = [str(s) for s in get_user_society_ids(user)]
            if str(society_id) not in society_ids:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You are not a supervisor of that society.")
            try:
                return Society.objects.get(pk=society_id)
            except Society.DoesNotExist:
                raise Http404

        return None

    def perform_create(self, serializer, **extra_kwargs):
        save_kwargs = dict(extra_kwargs)
        if self.society_field and self.society_field != 'id' and 'society' not in save_kwargs:
            society = self.resolve_create_society(self.request)
            if society:
                save_kwargs['society'] = society
        serializer.save(**save_kwargs)
