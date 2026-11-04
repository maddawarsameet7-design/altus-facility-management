import math
from datetime import datetime, time, timedelta
from typing import List, Tuple, Dict, Any, Optional
from django.core.exceptions import ValidationError
from django.utils import timezone


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in meters.
    """
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def is_within_geofence(worker_lat: float, worker_lng: float,
                       site_lat: float, site_lng: float,
                       radius_m: float, tolerance_m: float = 0.05) -> Tuple[bool, float]:
    """
    Check if worker GPS is within the site geofence radius.
    Allows a defined numerical tolerance (default 0.05 meters) for boundary precision.
    """
    dist = haversine_distance_meters(float(worker_lat), float(worker_lng),
                                      float(site_lat), float(site_lng))
    # Boundary check with tolerance
    is_inside = dist <= (radius_m + tolerance_m)
    return is_inside, dist


def parse_days_of_week(days_str: Any) -> List[int]:
    """
    Parse comma-separated days string e.g. '0,1,2,3,4,5,6' or list of ints into a list of ints.
    0 = Monday, 6 = Sunday.
    """
    if not days_str:
        return []
    if isinstance(days_str, list):
        res = []
        for x in days_str:
            try:
                val = int(x)
                if 0 <= val <= 6 and val not in res:
                    res.append(val)
            except (ValueError, TypeError):
                continue
        return res
    res = []
    for part in str(days_str).split(','):
        part = part.strip()
        if part.isdigit():
            val = int(part)
            if 0 <= val <= 6 and val not in res:
                res.append(val)
    return res


def get_shift_weekly_intervals(shift) -> List[Tuple[int, int]]:
    """
    Returns minute-intervals [start_minute, end_minute] across a 2-week continuous
    timeline (20,160 minutes) to seamlessly detect weekday and midnight-crossing overlaps.
    Week 0: 0 to 10080 minutes (Mon 00:00 to Sun 23:59).
    Week 1: 10080 to 20160 minutes.
    """
    days = parse_days_of_week(shift.days_of_week)
    start_min = shift.start_time.hour * 60 + shift.start_time.minute
    end_min = shift.end_time.hour * 60 + shift.end_time.minute
    duration = end_min - start_min
    if duration <= 0:
        duration += 1440  # Crosses midnight into next day

    intervals = []
    for week_offset in (0, 10080):
        for d in days:
            interval_start = week_offset + (d * 1440) + start_min
            interval_end = interval_start + duration
            intervals.append((interval_start, interval_end))

    return intervals


def shifts_overlap(shift1, shift2) -> bool:
    """
    Determine if shift1 and shift2 have overlapping operating minutes.
    """
    intervals1 = get_shift_weekly_intervals(shift1)
    intervals2 = get_shift_weekly_intervals(shift2)

    for s1, e1 in intervals1:
        for s2, e2 in intervals2:
            if max(s1, s2) < min(e1, e2):
                return True
    return False


def dates_overlap(start1, end1, start2, end2) -> bool:
    """
    Check if two date ranges [start1, end1] and [start2, end2] overlap.
    None indicates open-ended future.
    """
    if end1 is not None and start2 > end1:
        return False
    if end2 is not None and start1 > end2:
        return False
    return True


def calculate_schedule_warnings(worker, new_assignment=None) -> List[str]:
    """
    Calculate non-blocking warnings for:
    1. Working hours > 12h in any single calendar day.
    2. No weekly off in any rolling 7-day period.
    """
    from .models import RosterAssignment
    warnings = []

    assignments = list(RosterAssignment.objects.filter(
        worker=worker,
        status='ACTIVE'
    ).select_related('shift'))

    if new_assignment and new_assignment not in assignments:
        assignments.append(new_assignment)

    daily_minutes = {d: 0 for d in range(7)}
    for asgn in assignments:
        shift = asgn.shift
        s_min = shift.start_time.hour * 60 + shift.start_time.minute
        e_min = shift.end_time.hour * 60 + shift.end_time.minute
        dur = e_min - s_min
        if dur <= 0:
            dur += 1440
        days = parse_days_of_week(shift.days_of_week)
        for d in days:
            daily_minutes[d] += dur

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for d, mins in daily_minutes.items():
        if mins > 720:  # 12 hours = 720 minutes
            warnings.append(f"Scheduled hours exceed 12h on {day_names[d]} ({round(mins/60, 1)}h).")

    active_days = {d for d, mins in daily_minutes.items() if mins > 0}
    if len(active_days) == 7:
        warnings.append("Worker has shifts scheduled on all 7 days of the week with no weekly off.")

    return warnings


# ─── REPLACEMENT WORKFLOW ENGINE ─────────────────────────────────────────────

def check_worker_hard_blocks(worker, slot, min_rest_gap_hours: int = 8) -> Tuple[bool, Optional[str], List[str]]:
    """
    Checks if worker is strictly ineligible to cover the given DailyRoster slot.
    Returns: (is_blocked: bool, block_reason: Optional[str], warnings: List[str])

    Hard blocks (cannot be bypassed by normal supervisor):
      1. Not verified or suspended
      2. Approved leave on slot.date
      3. Overlapping shift datetime interval across ANY society
      4. Rest gap between consecutive shifts < min_rest_gap_hours
    """
    from .models import LeaveRecord, DailyRoster

    # 1. Verification status
    if getattr(worker, 'verification_status', '') != 'VERIFIED':
        return True, "Worker account is not verified.", []
    if getattr(worker, 'status', '') == 'SUSPENDED':
        return True, "Worker account is suspended.", []

    # 2. Approved leave on slot.date
    on_leave = LeaveRecord.objects.filter(
        worker=worker,
        start_date__lte=slot.date,
        end_date__gte=slot.date,
        status='APPROVED'
    ).exists()
    if on_leave:
        return True, f"Worker is on approved leave on {slot.date.isoformat()}.", []

    target_start = slot.shift_start_at
    target_end = slot.shift_end_at

    # 3. Cross-society shift interval overlap and rest gap
    # Search all slots where worker is scheduled or covered in window [target_start - 24h, target_end + 24h]
    window_start = target_start - timedelta(hours=24)
    window_end = target_end + timedelta(hours=24)

    nearby_slots = DailyRoster.objects.filter(
        shift_start_at__lt=window_end,
        shift_end_at__gt=window_start
    ).filter(
        # Worker is scheduled or covering
        models_q_worker_in_slot(worker)
    ).exclude(id=slot.id).select_related('shift', 'post')

    daily_minutes_on_date = (target_end - target_start).total_seconds() / 60

    for existing in nearby_slots:
        # Check overlap
        if max(target_start, existing.shift_start_at) < min(target_end, existing.shift_end_at):
            return True, f"Shift overlaps with worker's existing shift '{existing.shift.name}'.", []

        # Check rest gap (both before and after)
        if existing.shift_end_at <= target_start:
            gap_hours = (target_start - existing.shift_end_at).total_seconds() / 3600.0
            if gap_hours < min_rest_gap_hours:
                return True, f"Rest gap before shift is {round(gap_hours, 1)}h (minimum {min_rest_gap_hours}h required).", []

        if target_end <= existing.shift_start_at:
            gap_hours = (existing.shift_start_at - target_end).total_seconds() / 3600.0
            if gap_hours < min_rest_gap_hours:
                return True, f"Rest gap after shift is {round(gap_hours, 1)}h (minimum {min_rest_gap_hours}h required).", []

        if existing.date == slot.date:
            dur = (existing.shift_end_at - existing.shift_start_at).total_seconds() / 60
            daily_minutes_on_date += dur

    warnings = []
    if daily_minutes_on_date > 720:  # > 12 hours
        warnings.append(f"Total scheduled hours on {slot.date.isoformat()} would reach {round(daily_minutes_on_date/60, 1)}h (> 12h/day).")

    return False, None, warnings


def models_q_worker_in_slot(worker):
    from django.db.models import Q
    return Q(worker=worker, status__in=['SCHEDULED', 'PRESENT', 'COMPLETED']) | Q(covered_by=worker, status__in=['COVERED', 'COMPLETED'])


def rank_replacement_candidates(replacement_request) -> List[Dict[str, Any]]:
    """
    Ranks all eligible reliever workers for a given ReplacementRequest.
    Uses home pincode/area for proximity (NEVER live GPS of off-duty workers).
    Returns list of dicts ordered by highest score.
    """
    from .models import WorkerProfile, DailyRoster, AttendanceEvent, Alert

    slot = replacement_request.roster_entry
    site = slot.post.site
    post = slot.post
    settings_obj = getattr(replacement_request.society, 'settings', None)
    min_rest = getattr(settings_obj, 'min_rest_gap_hours', 8) if settings_obj else 8

    # All verified workers across platform (workers are deployed across societies)
    all_workers = WorkerProfile.objects.filter(
        verification_status='VERIFIED'
    ).select_related('user')

    candidates = []

    # Get Monday of slot's week
    week_start = slot.date - timedelta(days=slot.date.weekday())
    week_end = week_start + timedelta(days=6)

    for w in all_workers:
        is_blocked, block_reason, warnings = check_worker_hard_blocks(w, slot, min_rest_gap_hours=min_rest)
        if is_blocked:
            continue

        score = 0
        reasons = []

        # 1. Bench Availability on slot.date (+40 pts)
        has_shift_today = DailyRoster.objects.filter(
            date=slot.date
        ).filter(
            models_q_worker_in_slot(w)
        ).exclude(id=slot.id).exists()

        if not has_shift_today:
            score += 40
            reasons.append("Available on bench today (+40 pts)")
        else:
            reasons.append("Working another non-overlapping shift today (+0 pts)")

        # 2. Category Match (+15 pts)
        w_category = getattr(w, 'category', 'HOUSEKEEPING') or 'HOUSEKEEPING'
        if w_category.upper() == post.category.upper():
            score += 15
            reasons.append(f"Category match ({post.category}) (+15 pts)")

        # 3. Proximity via Home Area/Pincode (+15 pts max) — NEVER off-duty live GPS
        w_pincode = getattr(w, 'home_pincode', '') or ''
        site_pincode = getattr(site, 'pincode', '') or ''
        w_area = getattr(w, 'home_area', '') or ''
        site_area = getattr(site, 'area_name', '') or ''

        if w_pincode and site_pincode and w_pincode.strip() == site_pincode.strip():
            score += 15
            reasons.append(f"Home pincode match ({w_pincode}) (+15 pts)")
        elif w_area and site_area and (w_area.lower() in site_area.lower() or site_area.lower() in w_area.lower()):
            score += 10
            reasons.append(f"Home area proximity ({w_area}) (+10 pts)")

        # 4. Reliability Score (Attendance vs No-Shows/Absent) (+20 pts max)
        total_slots = DailyRoster.objects.filter(worker=w, date__lt=slot.date).count()
        absent_count = Alert.objects.filter(roster_entry__worker=w, alert_type='ABSENT').count()
        if total_slots > 0:
            completed_ratio = max(0.0, float(total_slots - absent_count) / float(total_slots))
            rel_score = int(completed_ratio * 20)
            score += rel_score
            reasons.append(f"Reliability history ({int(completed_ratio*100)}% attendance) (+{rel_score} pts)")
        else:
            score += 15  # Neutral starting score for newly verified worker
            reasons.append("Reliability baseline (+15 pts)")

        # 5. Fewer hours worked this week (+10 pts max)
        weekly_slots = DailyRoster.objects.filter(
            date__gte=week_start,
            date__lte=week_end
        ).filter(models_q_worker_in_slot(w))

        weekly_hours = 0.0
        for s in weekly_slots:
            weekly_hours += (s.shift_end_at - s.shift_start_at).total_seconds() / 3600.0

        if weekly_hours < 20:
            score += 10
            reasons.append(f"Low weekly workload ({round(weekly_hours, 1)}h worked) (+10 pts)")
        elif weekly_hours < 35:
            score += 5
            reasons.append(f"Moderate weekly workload ({round(weekly_hours, 1)}h worked) (+5 pts)")

        candidates.append({
            "worker_id": str(w.id),
            "name": f"{w.user.first_name} {w.user.last_name}".strip() or w.user.username,
            "score": score,
            "reasons": reasons,
            "warnings": warnings,
            "hours_this_week": round(weekly_hours, 1),
            "home_pincode": w_pincode,
            "home_area": w_area
        })

    # Sort descending by score
    candidates.sort(key=lambda c: c['score'], reverse=True)
    return candidates
