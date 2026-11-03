from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import DailyRoster, Alert, LeaveRecord


class Command(BaseCommand):
    help = "Mark absent slots when scheduled shift started and no clock-in occurred."

    def add_arguments(self, parser):
        parser.add_argument(
            '--grace-minutes',
            type=int,
            default=60,
            help="Grace window in minutes after shift start before marking absent."
        )

    def handle(self, *args, **options):
        grace_minutes = options['grace_minutes']
        now = timezone.now()
        threshold = now - timedelta(minutes=grace_minutes)

        # Slots whose shift began before threshold and have no attendance event
        unattended_slots = DailyRoster.objects.filter(
            shift_start_at__lte=threshold,
            attendance_event__isnull=True,
            status__in=['SCHEDULED', 'UNFILLED']
        ).select_related('society', 'worker__user', 'shift')

        absent_count = 0
        unfilled_count = 0

        for slot in unattended_slots:
            if slot.worker is not None:
                # Check if worker has an approved leave for this date
                has_approved_leave = LeaveRecord.objects.filter(
                    worker=slot.worker,
                    start_date__lte=slot.date,
                    end_date__gte=slot.date,
                    status='APPROVED'
                ).exists()

                if has_approved_leave:
                    slot.worker = None
                    slot.status = 'UNFILLED'
                    slot.save(update_fields=['worker', 'status', 'updated_at'])
                    Alert.objects.get_or_create(
                        society=slot.society,
                        roster_entry=slot,
                        alert_type='UNFILLED',
                        defaults={'notes': 'Worker has approved leave; shift left unfilled.'}
                    )
                    unfilled_count += 1
                else:
                    slot.status = 'ABSENT'
                    slot.save(update_fields=['status', 'updated_at'])
                    Alert.objects.get_or_create(
                        society=slot.society,
                        roster_entry=slot,
                        alert_type='ABSENT',
                        defaults={'notes': f"Worker {slot.worker.user.username} did not clock in within {grace_minutes}m grace."}
                    )
                    absent_count += 1
            else:
                # Empty slot remains UNFILLED with an alert
                slot.status = 'UNFILLED'
                slot.save(update_fields=['status', 'updated_at'])
                Alert.objects.get_or_create(
                    society=slot.society,
                    roster_entry=slot,
                    alert_type='UNFILLED',
                    defaults={'notes': f"Slot #{slot.slot_number} on {slot.shift.name} had no worker assigned."}
                )
                unfilled_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Evaluated unattended slots: Marked {absent_count} ABSENT, {unfilled_count} UNFILLED."
        ))

