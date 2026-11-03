import math
from datetime import datetime, time, timedelta
from typing import List, Tuple, Dict, Any
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


def parse_days_of_week(days_str: str) -> List[int]:
    """
    Parse comma-separated days string e.g. '0,1,2,3,4,5,6' into a list of ints.
    0 = Monday, 6 = Sunday.
    """
    if not days_str:
        return []
    res = []
    for part in days_str.split(','):
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
    # Replicate across 2 consecutive weeks to catch Sunday -> Monday overnight wrap
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
            # Check overlap in time
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

    # Gather all active assignments for worker across ALL societies
    assignments = list(RosterAssignment.objects.filter(
        worker=worker,
        status='ACTIVE'
    ).select_related('shift'))

    if new_assignment and new_assignment not in assignments:
        assignments.append(new_assignment)

    # 1. Check daily minutes per weekday (0 to 6)
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

    # 2. Check if all 7 days have scheduled shifts (no weekly off)
    active_days = {d for d, mins in daily_minutes.items() if mins > 0}
    if len(active_days) == 7:
        warnings.append("Worker has shifts scheduled on all 7 days of the week with no weekly off.")

    return warnings

