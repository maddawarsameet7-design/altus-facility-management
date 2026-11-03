"""
Migration 0007: Add direct society FK to Attendance, backfill from assignment.request,
and update InviteCode code field and upload_to handlers.
"""
import django.db.models.deletion
from django.db import migrations, models
import core.models


def backfill_attendance_society(apps, schema_editor):
    Attendance = apps.get_model('core', 'Attendance')
    for att in Attendance.objects.select_related('assignment__request__society').all():
        if att.assignment and att.assignment.request and att.assignment.request.society:
            att.society = att.assignment.request.society
            att.save(update_fields=['society'])


def reverse_backfill(apps, schema_editor):
    Attendance = apps.get_model('core', 'Attendance')
    Attendance.objects.all().update(society=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_backfill_default_society'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='assignment',
            options={'ordering': ['-assigned_at']},
        ),
        migrations.AlterModelOptions(
            name='attendance',
            options={'ordering': ['-clock_in']},
        ),
        migrations.AlterModelOptions(
            name='chatmessage',
            options={'ordering': ['timestamp']},
        ),
        migrations.AlterModelOptions(
            name='invitecode',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='paymenttransaction',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='review',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='servicecategory',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='servicerequest',
            options={'ordering': ['-created_at']},
        ),
        migrations.AlterModelOptions(
            name='site',
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='attendance',
            name='society',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='attendances',
                to='core.society'
            ),
        ),
        migrations.AlterField(
            model_name='attendance',
            name='photo_proof',
            field=models.ImageField(blank=True, null=True, upload_to=core.models.upload_attendance_proof),
        ),
        migrations.AlterField(
            model_name='invitecode',
            name='code',
            field=models.CharField(default=core.models._generate_invite_code, max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='workerprofile',
            name='id_document',
            field=models.FileField(blank=True, null=True, upload_to=core.models.upload_worker_doc),
        ),
        migrations.AlterField(
            model_name='workerprofile',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to=core.models.upload_worker_photo),
        ),
        migrations.RunPython(backfill_attendance_society, reverse_backfill),
    ]
