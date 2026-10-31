"""
Migration 0006: Data migration — create Default Society, backfill Memberships
and ServiceRequests, and create default SocietySettings.

Safe to run against an existing database with live data.
After running, confirm no nulls remain before making society non-null:
    python manage.py shell -c "from core.models import ServiceRequest; print(ServiceRequest.objects.filter(society__isnull=True).count())"
"""
from django.db import migrations


ROLES_FOR_MEMBERSHIP = ('MEMBER', 'CHAIRMAN', 'SUPERVISOR')


def create_default_society(apps, schema_editor):
    Society = apps.get_model('core', 'Society')
    SocietySettings = apps.get_model('core', 'SocietySettings')
    Membership = apps.get_model('core', 'Membership')
    User = apps.get_model('core', 'User')
    ServiceRequest = apps.get_model('core', 'ServiceRequest')

    # 1. Create the Default Society (idempotent)
    default_society, created = Society.objects.get_or_create(
        name='Default Society',
        defaults={
            'client_type': 'SOCIETY',
            'address': 'To be updated',
            'is_active': True,
        }
    )

    # 2. Create its settings
    SocietySettings.objects.get_or_create(society=default_society)

    # 3. Create Memberships for all existing non-Director, non-Worker users
    for user in User.objects.filter(role__in=ROLES_FOR_MEMBERSHIP):
        # Map platform role to membership role
        membership_role = user.role  # MEMBER→MEMBER, CHAIRMAN→CHAIRMAN, SUPERVISOR→SUPERVISOR
        Membership.objects.get_or_create(
            user=user,
            society=default_society,
            defaults={
                'role': membership_role,
                'is_active': True,
            }
        )

    # 4. Backfill all ServiceRequests to the Default Society
    ServiceRequest.objects.filter(society__isnull=True).update(society=default_society)


def reverse_default_society(apps, schema_editor):
    """Reverse: null out society on ServiceRequests, delete Memberships and Society."""
    Society = apps.get_model('core', 'Society')
    Membership = apps.get_model('core', 'Membership')
    ServiceRequest = apps.get_model('core', 'ServiceRequest')

    try:
        default = Society.objects.get(name='Default Society')
        ServiceRequest.objects.filter(society=default).update(society=None)
        Membership.objects.filter(society=default).delete()
        default.delete()
    except Society.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_society_multitenancy'),
    ]

    operations = [
        migrations.RunPython(create_default_society, reverse_default_society),
    ]

