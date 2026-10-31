"""
Helper used by T14 test to call the backfill logic without re-running migrations.
"""
from core.models import Membership


ROLES_FOR_MEMBERSHIP = ('MEMBER', 'CHAIRMAN', 'SUPERVISOR')


def backfill_memberships_for_society(society, users):
    """Create Memberships for a list of users in the given society."""
    for user in users:
        if user.role not in ROLES_FOR_MEMBERSHIP:
            continue
        Membership.objects.get_or_create(
            user=user,
            society=society,
            defaults={'role': user.role, 'is_active': True}
        )

