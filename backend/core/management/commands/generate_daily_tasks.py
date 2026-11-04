import calendar
import zoneinfo
from datetime import datetime, timedelta, timezone as dt_tz
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.models import TaskTemplate, TaskInstance, DailyRoster
from core.staffing_utils import parse_days_of_week


class Command(BaseCommand):
    help = "Generate daily housekeeping TaskInstances from active TaskTemplates."

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None, help="Target date (YYYY-MM-DD), defaults to today.")
        parser.add_argument('--days', type=int, default=1, help="Number of days forward to generate tasks for.")

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            start_date = parse_date(date_str) or timezone.localdate()
        else:
            start_date = timezone.localdate()

        days_count = options.get('days') or 1

        try:
            kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        except Exception:
            from zoneinfo import ZoneInfo
            kolkata_tz = ZoneInfo("Asia/Kolkata")

        created_count = 0
        existing_count = 0
        skipped_inactive = 0

        for day_offset in range(days_count):
            target_date = start_date + timedelta(days=day_offset)
            weekday_int = target_date.weekday()  # 0=Monday ... 6=Sunday
            last_day_of_month = calendar.monthrange(target_date.year, target_date.month)[1]

            # Amendment 7: Skip inactive templates, inactive posts, inactive shifts, inactive areas
            templates = TaskTemplate.objects.filter(
                is_active=True,
                effective_from__lte=target_date,
                post__is_active=True,
                shift__is_active=True,
                area__is_active=True
            ).filter(
                models_q_effective_to(target_date)
            ).select_related('society', 'post', 'shift', 'area')

            for tmpl in templates:
                shift = tmpl.shift

                # Amendment 7 & 13: Generation respects Shift.days_of_week
                shift_days = parse_days_of_week(shift.days_of_week)
                if weekday_int not in shift_days:
                    continue

                # Template Frequency Matching
                if tmpl.frequency == 'DAILY':
                    should_generate = True
                elif tmpl.frequency == 'WEEKLY':
                    tmpl_days = parse_days_of_week(tmpl.days_of_week)
                    should_generate = (weekday_int in tmpl_days)
                elif tmpl.frequency == 'MONTHLY':
                    target_day = tmpl.day_of_month or 1
                    # Short month rule: if month shorter, use its last day
                    effective_day = min(target_day, last_day_of_month)
                    should_generate = (target_date.day == effective_day)
                else:
                    should_generate = False

                if not should_generate:
                    continue

                # Compute timezone-aware shift start and end (UTC)
                roster_slot = DailyRoster.objects.filter(
                    shift=shift,
                    date=target_date
                ).first()

                if roster_slot and roster_slot.shift_start_at and roster_slot.shift_end_at:
                    start_dt = roster_slot.shift_start_at
                    end_dt = roster_slot.shift_end_at
                else:
                    start_naive = datetime.combine(target_date, shift.start_time)
                    start_dt = timezone.make_aware(start_naive, kolkata_tz).astimezone(dt_tz.utc)
                    if shift.crosses_midnight:
                        end_naive = datetime.combine(target_date + timedelta(days=1), shift.end_time)
                    else:
                        end_naive = datetime.combine(target_date, shift.end_time)
                    end_dt = timezone.make_aware(end_naive, kolkata_tz).astimezone(dt_tz.utc)

                # Amendment 5: Copy name, photo_required and estimated_minutes onto TaskInstance at generation
                # Amendment 7: Preserved even if roster slot is UNFILLED or ABSENT
                instance, created = TaskInstance.objects.get_or_create(
                    template=tmpl,
                    due_date=target_date,
                    is_rework=False,
                    defaults={
                        'society': tmpl.society,
                        'post': tmpl.post,
                        'shift': tmpl.shift,
                        'area': tmpl.area,
                        'name': tmpl.name,
                        'photo_required': tmpl.photo_required,
                        'estimated_minutes': tmpl.estimated_minutes,
                        'shift_start_at': start_dt,
                        'shift_end_at': end_dt,
                        'status': 'PENDING'
                    }
                )

                if created:
                    created_count += 1
                else:
                    existing_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Daily task generation complete. Created: {created_count}, Existing: {existing_count}."
        ))


def models_q_effective_to(target_date):
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=target_date)
