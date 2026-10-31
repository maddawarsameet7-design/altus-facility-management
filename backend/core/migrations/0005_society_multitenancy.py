"""
Migration 0005: Add Society, Site, Membership, SocietySettings, InviteCode
and add nullable society FK to ServiceRequest.
"""
import uuid
import random
import string
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _gen_code():
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ALTUS-{suffix}"


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_attendance_photo_proof_workerprofile_id_document_and_more'),
    ]

    operations = [
        # ── Society ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Society',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('client_type', models.CharField(
                    choices=[('SOCIETY', 'Housing Society'), ('HOSPITAL', 'Hospital / Healthcare'), ('OFFICE', 'Corporate / Office')],
                    default='SOCIETY', max_length=20
                )),
                ('address', models.TextField()),
                ('gstin', models.CharField(blank=True, max_length=20, null=True)),
                ('billing_email', models.EmailField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name_plural': 'Societies', 'ordering': ['name']},
        ),

        # ── Site ─────────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('society', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sites', to='core.society')),
                ('name', models.CharField(max_length=255)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('geofence_radius_m', models.IntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),

        # ── Membership ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Membership',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to=settings.AUTH_USER_MODEL)),
                ('society', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='core.society')),
                ('role', models.CharField(
                    choices=[('MEMBER', 'Member'), ('CHAIRMAN', 'Chairman'), ('SUPERVISOR', 'Supervisor')],
                    default='MEMBER', max_length=20
                )),
                ('flat_or_unit', models.CharField(blank=True, max_length=50, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-joined_at'], 'unique_together': {('user', 'society')}},
        ),

        # ── SocietySettings ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='SocietySettings',
            fields=[
                ('society', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True, related_name='settings',
                    serialize=False, to='core.society'
                )),
                ('selfie_required', models.BooleanField(default=False)),
                ('shift_start_grace_minutes', models.IntegerField(default=15)),
                ('overtime_policy', models.CharField(
                    choices=[('NONE', 'No Overtime Policy'), ('FLAT', 'Flat Overtime Rate'), ('MULTIPLIER', 'Multiplier-based Overtime')],
                    default='NONE', max_length=20
                )),
                ('invoice_day', models.IntegerField(
                    default=1,
                    validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(28)]
                )),
                ('payment_terms_days', models.IntegerField(default=30)),
            ],
            options={'verbose_name_plural': 'Society Settings'},
        ),

        # ── InviteCode ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='InviteCode',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('society', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invite_codes', to='core.society')),
                ('role', models.CharField(
                    choices=[('MEMBER', 'Member'), ('CHAIRMAN', 'Chairman'), ('SUPERVISOR', 'Supervisor')],
                    default='MEMBER', max_length=20
                )),
                ('code', models.CharField(default=_gen_code, max_length=20, unique=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('max_uses', models.IntegerField(default=1)),
                ('use_count', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),

        # ── society FK on ServiceRequest (nullable) ──────────────────────────
        migrations.AddField(
            model_name='servicerequest',
            name='society',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='service_requests',
                to='core.society'
            ),
        ),
    ]

