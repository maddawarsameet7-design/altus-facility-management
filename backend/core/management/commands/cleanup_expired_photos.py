from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import TaskPhoto, Society


class Command(BaseCommand):
    help = "Cleanup expired housekeeping task photos beyond the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report expired photos without deleting files or records.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        total_scanned = 0
        total_deleted = 0

        societies = Society.objects.filter(is_active=True).select_related('settings')

        for society in societies:
            retention_days = 90
            if hasattr(society, 'settings') and society.settings:
                retention_days = society.settings.photo_retention_days or 90

            cutoff = now - timedelta(days=retention_days)
            expired_photos = TaskPhoto.objects.filter(
                society=society,
                created_at__lt=cutoff
            )

            count = expired_photos.count()
            total_scanned += count

            if not dry_run and count > 0:
                for photo in expired_photos:
                    try:
                        if photo.file:
                            photo.file.delete(save=False)
                        if photo.thumbnail:
                            photo.thumbnail.delete(save=False)
                    except Exception as e:
                        self.stderr.write(f"Failed to delete storage file for photo {photo.id}: {e}")
                    photo.delete()
                    total_deleted += 1

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY RUN] {total_scanned} expired photos eligible for deletion."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Photo cleanup complete. Deleted {total_deleted} expired photos."
            ))
