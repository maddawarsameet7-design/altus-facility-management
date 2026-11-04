import zoneinfo
from datetime import datetime, timedelta, timezone as dt_tz
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import Shift, RosterAssignment, DailyRoster, LeaveRecord, ReplacementRequest
from core.staffing_utils import parse_days_of_week


class Command(BaseCommand):
    help = "Generate DailyRoster slots from active RosterAssignments for the next N days."

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help="Number of days to generate roster for.")
        parser.add_argument('--date', type=str, default=None, help="Start date (YYYY-MM-DD), defaults to today.")

    def handle(self, *args, **options):
        days = options['days']
        start_date_str = options.get('date')
        if start_date_str:
            start_date = parse_date(start_date_str) or timezone.localdate()
        else:
            start_date = timezone.localdate()

        now = timezone.now()
        try:
            kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        except Exception:
            from zoneinfo import ZoneInfo
            kolkata_tz = ZoneInfo("Asia/Kolkata")

        created_count = 0
        updated_count = 0

        shifts = Shift.objects.filter(is_active=True).select_related('post', 'society')

        for day_offset in range(days):
            target_date = start_date + timedelta(days=day_offset)
            weekday_int = target_date.weekday()  # 0=Monday ... 6=Sunday

            for shift in shifts:
                operating_days = parse_days_of_week(shift.days_of_week)
                if weekday_int not in operating_days:
                    continue

                # Compute timezone-aware shift start and end
                start_naive = datetime.combine(target_date, shift.start_time)
                start_dt = timezone.make_aware(start_naive, kolkata_tz).astimezone(dt_tz.utc)

                if shift.crosses_midnight:
                    end_naive = datetime.combine(target_date + timedelta(days=1), shift.end_time)
                else:
                    end_naive = datetime.combine(target_date, shift.end_time)
                end_dt = timezone.make_aware(end_naive, kolkata_tz).astimezone(dt_tz.utc)

                # Find active assignments for this shift on target_date
                active_assignments = list(RosterAssignment.objects.filter(
                    shift=shift,
                    status='ACTIVE',
                    start_date__lte=target_date
                ).filter(
                    models_q_end_date(target_date)
                ).select_related('worker').order_by('created_at'))

                # Filter out workers who have approved leave on target_date
                available_workers = []
                for asgn in active_assignments:
                    has_leave = LeaveRecord.objects.filter(
                        worker=asgn.worker,
                        start_date__lte=target_date,
                        end_date__gte=target_date,
                        status='APPROVED'
                    ).exists()
                    if not has_leave:
                        available_workers.append(asgn.worker)

                required_count = shift.required_headcount or 1

                for slot_num in range(1, required_count + 1):
                    assigned_worker = available_workers[slot_num - 1] if (slot_num - 1) < len(available_workers) else None
                    target_status = 'SCHEDULED' if assigned_worker else 'UNFILLED'

                    slot, created = DailyRoster.objects.get_or_create(
                        shift=shift,
                        date=target_date,
                        slot_number=slot_num,
                        defaults={
                            'society': shift.society,
                            'post': shift.post,
                            'worker': assigned_worker,
                            'status': target_status,
                            'shift_start_at': start_dt,
                            'shift_end_at': end_dt
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        # Amendment 4: May update future slots with no attendance when assignments change,
                        # never past slots, slots with attendance, or already COVERED replacement slots.
                        if target_date >= start_date and slot.shift_start_at > now and not hasattr(slot, 'attendance_event') and slot.status != 'COVERED':
                            if slot.worker != assigned_worker or slot.shift_start_at != start_dt or slot.shift_end_at != end_dt:
                                slot.worker = assigned_worker
                                slot.status = target_status
                                slot.shift_start_at = start_dt
                                slot.shift_end_at = end_dt
                                slot.save(update_fields=['worker', 'status', 'shift_start_at', 'shift_end_at', 'updated_at'])
                                updated_count += 1

                    # Amendment 4: Auto-open ReplacementRequest for unfilled slots close to start (<= 24h)
                    if slot.status == 'UNFILLED' and now < slot.shift_start_at <= (now + timedelta(hours=24)):
                        if not ReplacementRequest.objects.filter(roster_entry=slot, status__in=['OPEN', 'OFFERING', 'ESCALATED']).exists():
                            ReplacementRequest.objects.create(
                                society=shift.society,
                                roster_entry=slot,
                                reason='UNFILLED',
                                status='OPEN'
                            )

        self.stdout.write(self.style.SUCCESS(
            f"Roster generation complete for {days} days from {start_date}. "
            f"Created: {created_count}, Updated future: {updated_count}."
        ))


def models_q_end_date(target_date):
    from django.db.models import Q
    return Q(end_date__isnull=True) | Q(end_date__gte=target_date)

