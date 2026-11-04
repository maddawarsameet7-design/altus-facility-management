import logging
import re
from django.db import migrations

logger = logging.getLogger('core.migrations')


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r'[\s\-\(\)]', '', str(phone).strip())
    if cleaned.isdigit() and len(cleaned) == 10:
        cleaned = f"+91{cleaned}"
    elif cleaned.isdigit() and len(cleaned) == 12 and cleaned.startswith('91'):
        cleaned = f"+{cleaned}"
    elif cleaned.isdigit() and not cleaned.startswith('+'):
        cleaned = f"+{cleaned}"
    return cleaned


def normalize_and_report_worker_phones(apps, schema_editor):
    WorkerProfile = apps.get_model('core', 'WorkerProfile')

    seen_phones = {}
    duplicates = {}
    invalid_phones = []
    to_update = []

    for wp in WorkerProfile.objects.select_related('user').all():
        raw_phone = wp.phone or ""
        norm_phone = normalize_phone(raw_phone)

        # Check E.164 format: + followed by 8 to 15 digits
        if not re.match(r'^\+[1-9]\d{7,14}$', norm_phone):
            invalid_phones.append({
                "worker_id": str(wp.id),
                "username": getattr(wp.user, 'username', 'unknown'),
                "raw_phone": raw_phone
            })

        if norm_phone in seen_phones:
            if norm_phone not in duplicates:
                duplicates[norm_phone] = [seen_phones[norm_phone]]
            duplicates[norm_phone].append({
                "worker_id": str(wp.id),
                "username": getattr(wp.user, 'username', 'unknown'),
                "raw_phone": raw_phone
            })
        else:
            seen_phones[norm_phone] = {
                "worker_id": str(wp.id),
                "username": getattr(wp.user, 'username', 'unknown'),
                "raw_phone": raw_phone
            }
            to_update.append((wp, norm_phone))

    # Report results explicitly (never silently fix duplicates or invalid numbers)
    print("\n" + "=" * 70)
    print("PHONE NORMALIZATION & AUDIT REPORT (Migration 0012)")
    print("=" * 70)

    if invalid_phones:
        print(f"[WARNING] INVALID PHONE NUMBERS DETECTED ({len(invalid_phones)}):")
        for inv in invalid_phones:
            print(f"   - Worker: {inv['username']} (ID: {inv['worker_id']}) -> Raw: '{inv['raw_phone']}'")
        print("   -> Action required: Contact operations to update phone before enforcing strict format.")
    else:
        print("[OK] All worker phone numbers conform to valid numerical formats.")

    if duplicates:
        print(f"\n[DUPLICATE] DUPLICATE PHONE NUMBERS DETECTED ({len(duplicates)} duplicate groups):")
        for phone, workers in duplicates.items():
            print(f"   - Normalized Phone: {phone}")
            for w in workers:
                print(f"       * Worker: {w['username']} (ID: {w['worker_id']}) | Raw: '{w['raw_phone']}'")
        print("\n   [SAFETY NOTICE] Migration will NOT silently overwrite, merge, or delete duplicate phone numbers.")
        print("   If you are running in dev/test, duplicate dev accounts will need distinct phone numbers before 0013 unique constraint applies.")
    else:
        print("[OK] No duplicate phone numbers found across WorkerProfiles.")

    print("=" * 70 + "\n")

    # Normalize valid non-conflicting numbers
    conflicting_worker_ids = set()
    for grp in duplicates.values():
        for item in grp:
            conflicting_worker_ids.add(item['worker_id'])

    for wp, norm_phone in to_update:
        if str(wp.id) not in conflicting_worker_ids and wp.phone != norm_phone:
            wp.phone = norm_phone
            wp.save(update_fields=['phone'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_otpchallenge'),
    ]

    operations = [
        migrations.RunPython(
            normalize_and_report_worker_phones,
            reverse_code=migrations.RunPython.noop
        ),
    ]
