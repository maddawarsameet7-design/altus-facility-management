from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import TaskInstance


class Command(BaseCommand):
    help = "Mark pending, in-progress, or evidence-expired tasks as MISSED."

    def handle(self, *args, **options):
        now = timezone.now()
        missed_count = 0

        # 1. PENDING and IN_PROGRESS tasks whose shift window + grace has elapsed
        open_tasks = TaskInstance.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            shift_end_at__lt=now
        ).select_related('society__settings')

        for task in open_tasks:
            grace_mins = 30
            if hasattr(task.society, 'settings') and task.society.settings:
                grace_mins = task.society.settings.task_missed_grace_minutes or 30

            cutoff = task.shift_end_at + timedelta(minutes=grace_mins)
            if now > cutoff:
                task.status = 'MISSED'
                note = "Shift ended without completion (Marked MISSED)."
                task.notes = f"{task.notes}\n{note}".strip() if task.notes else note
                task.save(update_fields=['status', 'notes', 'updated_at'])
                missed_count += 1

        # 2. AWAITING_EVIDENCE tasks whose evidence deadline has expired (Amendment 2)
        awaiting_tasks = TaskInstance.objects.filter(
            status='AWAITING_EVIDENCE'
        ).select_related('society__settings')

        for task in awaiting_tasks:
            deadline = task.evidence_deadline
            if not deadline:
                deadline_hours = 24
                if hasattr(task.society, 'settings') and task.society.settings:
                    deadline_hours = task.society.settings.evidence_deadline_hours or 24
                base_time = task.completed_at or task.shift_end_at
                deadline = base_time + timedelta(hours=deadline_hours)

            if now > deadline:
                task.status = 'MISSED'
                note = "Evidence deadline expired without required photos (Marked MISSED)."
                task.notes = f"{task.notes}\n{note}".strip() if task.notes else note
                task.save(update_fields=['status', 'notes', 'updated_at'])
                missed_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Missed task scan complete. Marked {missed_count} tasks as MISSED."
        ))

