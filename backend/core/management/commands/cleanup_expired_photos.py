from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import TaskPhoto, Society


import calendar
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from core.models import TaskPhoto, Society, Complaint, Inspection, QualityScoreSnapshot


class Command(BaseCommand):
    help = "Cleanup expired housekeeping task photos beyond the configured retention period. Defaults to dry-run."

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            default=False,
            help='Execute actual deletion of storage files and database records. Default is dry-run.'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Explicit dry-run mode (default behavior).'
        )

    def handle(self, *args, **options):
        # Default to dry-run unless --commit is explicitly passed without --dry-run
        is_dry_run = not options.get('commit') or options.get('dry_run')
        now = timezone.now()
        total_scanned = 0
        total_deleted = 0
        total_protected = 0

        societies = Society.objects.filter(is_active=True).select_related('settings')

        for society in societies:
            retention_days = 90
            if hasattr(society, 'settings') and society.settings:
                retention_days = society.settings.photo_retention_days or 90

            cutoff = now - timedelta(days=retention_days)
            candidates = TaskPhoto.objects.filter(
                society=society,
                created_at__lt=cutoff
            ).select_related('task_instance__post__site', 'task_instance__area')

            # ── 1. Protection Guards (Never Delete) ───────────────────────────
            # a) Photos tied to ACKNOWLEDGED complaints, any complaint not RESOLVED/REJECTED,
            # or any complaint disputed by client (even if marked resolved/rejected)
            unclosed_or_disputed_complaints = Complaint.objects.filter(society=society).filter(
                ~Q(status__in=['RESOLVED', 'REJECTED']) | Q(disputed_by_client=True)
            )
            protected_areas = set(unclosed_or_disputed_complaints.exclude(area__isnull=True).values_list('area_id', flat=True))
            protected_posts = set(unclosed_or_disputed_complaints.exclude(post__isnull=True).values_list('post_id', flat=True))

            # b) Photos tied to shared inspections
            shared_inspections = Inspection.objects.filter(society=society, shared_with_client=True)
            protected_inspection_keys = set(
                shared_inspections.values_list('date', 'post_id', 'area_id')
            )

            # c) Photos tied to locked monthly snapshots
            locked_snapshots = QualityScoreSnapshot.objects.filter(society=society, is_locked=True)
            protected_snapshot_months = set()
            for snap in locked_snapshots:
                # snap.month is 'YYYY-MM'
                try:
                    parts = snap.month.split('-')
                    y, m = int(parts[0]), int(parts[1])
                    protected_snapshot_months.add((str(snap.site_id), y, m))
                except (ValueError, IndexError):
                    continue

            for photo in candidates:
                total_scanned += 1
                task = photo.task_instance
                is_protected = False

                # Check complaint protection
                if task:
                    if task.area_id in protected_areas or task.post_id in protected_posts:
                        is_protected = True

                    # Check shared inspection protection
                    insp_key = (task.due_date, task.post_id, task.area_id)
                    if insp_key in protected_inspection_keys:
                        is_protected = True

                    # Check locked monthly snapshot protection
                    site_id = str(task.post.site_id) if (task.post and task.post.site_id) else None
                    if site_id and (site_id, task.due_date.year, task.due_date.month) in protected_snapshot_months:
                        is_protected = True

                if is_protected:
                    total_protected += 1
                    continue

                if not is_dry_run:
                    # Keep DB and storage strictly consistent
                    try:
                        with transaction.atomic():
                            if photo.file:
                                photo.file.delete(save=False)
                            if photo.thumbnail:
                                photo.thumbnail.delete(save=False)
                            photo.delete()
                            total_deleted += 1
                    except Exception as e:
                        self.stderr.write(f"Failed to delete storage file for photo {photo.id}: {e}")
                else:
                    total_deleted += 1

        if is_dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY RUN] {total_scanned} scanned. {total_deleted} eligible for deletion. "
                f"{total_protected} protected from deletion (complaints/inspections/snapshots)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Photo cleanup complete. Deleted {total_deleted} expired photos. "
                f"{total_protected} protected."
            ))

