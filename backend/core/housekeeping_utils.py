import calendar
import io
import math
import zoneinfo
from datetime import datetime, timedelta, timezone as dt_tz
from decimal import Decimal
from typing import Tuple, List, Optional, Dict, Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models import Avg, Q
from django.utils import timezone
from PIL import Image

from core.models import (
    Site, SocietySettings, TaskInstance, Inspection, Complaint,
    QualityScoreSnapshot
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS points in meters.
    """
    lat1, lon1 = float(lat1), float(lon1)
    lat2, lon2 = float(lat2), float(lon2)
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def process_and_sanitize_image(
    uploaded_file,
    max_size_bytes: int = 5 * 1024 * 1024,
    max_dimension: int = 4096,
    thumb_dimension: int = 300
) -> Tuple[ContentFile, ContentFile]:
    """
    Decodes, validates, sanitizes (strips EXIF), compresses, and generates a thumbnail for an image.
    Enforces:
    - File size <= max_size_bytes (5MB)
    - Image dimensions <= max_dimension (4096px)
    - Valid decodable image bytes
    - Stripped EXIF metadata for privacy
    Returns: (sanitized_image_content_file, thumbnail_content_file)
    """
    # 1. Size check
    uploaded_file.seek(0, io.SEEK_END)
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)

    if file_size > max_size_bytes:
        raise ValidationError(f"File size exceeds maximum allowed limit ({max_size_bytes // (1024*1024)}MB).")

    # 2. Decode bytes with Pillow
    try:
        img = Image.open(uploaded_file)
        img.verify()  # Fast structural verification
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)  # Reopen for actual processing
    except Exception as e:
        raise ValidationError(f"Invalid or undecodable image file: {e}")

    # 3. Dimension check
    width, height = img.size
    if width > max_dimension or height > max_dimension:
        raise ValidationError(f"Image dimensions ({width}x{height}) exceed maximum allowed {max_dimension}x{max_dimension}px.")

    # 4. Color mode conversion & EXIF stripping
    # Convert RGBA/P to RGB for clean JPEG encoding without metadata
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    else:
        # Create a fresh image copy to ensure all EXIF metadata tags are completely stripped
        fresh_img = Image.new('RGB', img.size)
        fresh_img.paste(img)
        img = fresh_img

    # 5. Compress & save full image to memory
    img_io = io.BytesIO()
    img.save(img_io, format='JPEG', quality=85, optimize=True)
    img_io.seek(0)
    sanitized_file = ContentFile(img_io.getvalue(), name="photo.jpg")

    # 6. Generate thumbnail
    thumb_img = img.copy()
    thumb_img.thumbnail((thumb_dimension, thumb_dimension), Image.Resampling.LANCZOS)
    thumb_io = io.BytesIO()
    thumb_img.save(thumb_io, format='JPEG', quality=75, optimize=True)
    thumb_io.seek(0)
    thumbnail_file = ContentFile(thumb_io.getvalue(), name="thumb.jpg")

    return sanitized_file, thumbnail_file


def validate_photo_capture_gps(
    site: Site,
    captured_at: datetime,
    lat: Optional[float],
    lng: Optional[float],
    gps_accuracy_m: Optional[float],
    is_mock: bool,
    shift_start_at: Optional[datetime] = None,
    shift_end_at: Optional[datetime] = None,
    policy: str = 'REJECT'
) -> Tuple[bool, Optional[str], List[str], Optional[float]]:
    """
    Validates capture-time GPS, timestamps, accuracy, and geofence.
    Returns: (is_allowed, rejection_reason, flags, distance_from_site_m)
    """
    now = timezone.now()
    flags: List[str] = []

    # 1. Future capture time validation (rejection)
    if captured_at > now + timedelta(minutes=5):
        return False, "Photo capture timestamp cannot be in the future.", flags, None

    # 2. Time mismatch check (> 15 minutes between capture and server receipt)
    if abs((now - captured_at).total_seconds()) > 900:
        flags.append('TIME_MISMATCH')

    # 3. Shift window check
    if shift_start_at and shift_end_at:
        early_bound = shift_start_at - timedelta(minutes=30)
        late_bound = shift_end_at + timedelta(minutes=30)
        if captured_at < early_bound or captured_at > late_bound:
            flags.append('OUTSIDE_SHIFT_WINDOW')

    # 4. Mock location flag
    if is_mock:
        flags.append('MOCK_LOCATION')

    # 5. GPS Geofence & Accuracy check
    distance: Optional[float] = None
    if lat is not None and lng is not None and site.latitude is not None and site.longitude is not None:
        distance = haversine_distance(site.latitude, site.longitude, lat, lng)

        # GPS accuracy check
        max_acc = site.max_gps_accuracy_m or 50.0
        if gps_accuracy_m is not None and gps_accuracy_m > max_acc:
            flags.append('LOW_ACCURACY')

        # Geofence check
        radius = site.geofence_radius_m or 100.0
        if distance > radius:
            if policy == 'REJECT':
                return False, f"Photo captured outside site geofence: {round(distance, 1)}m > {radius}m.", flags, distance
            else:
                flags.append('OUTSIDE_GEOFENCE')
    else:
        flags.append('NO_GPS_COORDINATES')

    return True, None, flags, distance


def calculate_monthly_quality_score(site: Site, year: int, month: int) -> Dict[str, Any]:
    """
    Computes quality score for a Site and Month according to Altus SLA specification:
      Score = w_c*T + w_i*I + w_k*C
    Honors:
    - Excused skips (AREA_LOCKED, RESIDENT_REQUEST, EXCUSED) excluded from denominator.
    - Unexcused skips (NO_SUPPLIES, OTHER) and MISSED tasks count as failures in denominator.
    - Tasks with needs_review=True excluded from completed numerator until supervisor approves.
    - Rework tasks counted once.
    - If 0 inspections: drops inspection weight and re-normalizes remaining weights.
    - If 0 complaints: drops complaint weight and re-normalizes remaining weights.
    - Unresolved complaints older than escalation window count as failures.
    - Rejected-but-disputed complaints remain in the denominator.
    """
    try:
        kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    except Exception:
        from zoneinfo import ZoneInfo
        kolkata_tz = ZoneInfo("Asia/Kolkata")

    settings = getattr(site.society, 'settings', None)
    w_c_raw = getattr(settings, 'completion_weight', 40) if settings else 40
    w_i_raw = getattr(settings, 'inspection_weight', 40) if settings else 40
    w_k_raw = getattr(settings, 'complaint_weight', 20) if settings else 20
    escalation_hours = getattr(settings, 'complaint_escalation_hours', 24) if settings else 24

    # Date boundaries in month
    first_date = datetime(year, month, 1).date()
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day).date()

    # ── 1. Task Completion Component (T) ──
    # All tasks scheduled for posts at this site
    month_tasks = TaskInstance.objects.filter(
        post__site=site,
        due_date__gte=first_date,
        due_date__lte=last_date
    )

    # Exclude rework duplicates from base denominator (rework counted once)
    base_tasks = month_tasks.filter(is_rework=False)

    total_tasks_count = base_tasks.count()
    excused_count = base_tasks.filter(
        Q(skip_reason__in=['AREA_LOCKED', 'RESIDENT_REQUEST', 'EXCUSED']) | Q(is_excused=True)
    ).count()

    denominator_tasks = total_tasks_count - excused_count
    if denominator_tasks <= 0:
        t_score = 100.0
    else:
        # Completed & approved tasks
        # (needs_review=True excluded until approved)
        completed_count = base_tasks.filter(
            status='DONE',
            needs_review=False
        ).count()
        t_score = (completed_count / denominator_tasks) * 100.0

    # ── 2. Inspection Component (I) ──
    inspections = Inspection.objects.filter(
        post__site=site,
        date__gte=first_date,
        date__lte=last_date
    )
    inspection_count = inspections.count()
    if inspection_count > 0:
        avg_score = inspections.aggregate(Avg('score'))['score__avg'] or 0.0
        i_score = (avg_score / 5.0) * 100.0
        has_inspections = True
    else:
        i_score = None
        has_inspections = False

    # ── 3. Complaint SLA Component (C) ──
    complaints = Complaint.objects.filter(
        site=site,
        created_at__year=year,
        created_at__month=month
    )
    complaint_count = complaints.count()

    if complaint_count > 0:
        now = timezone.now()
        resolved_in_sla = 0

        for comp in complaints:
            # Resolved complaints checked against SLA
            if comp.status == 'RESOLVED' and comp.resolved_at:
                dur_hours = (comp.resolved_at - comp.created_at).total_seconds() / 3600.0
                if dur_hours <= escalation_hours:
                    resolved_in_sla += 1
            elif comp.status == 'REJECTED' and not comp.disputed_by_client:
                # Valid undisputed rejection does not penalize
                resolved_in_sla += 1
            else:
                # Open/in-progress or disputed: check if already past SLA
                dur_hours = (now - comp.created_at).total_seconds() / 3600.0
                if dur_hours <= escalation_hours:
                    resolved_in_sla += 1  # Still within SLA window

        c_score = (resolved_in_sla / complaint_count) * 100.0
        has_complaints = True
    else:
        c_score = None
        has_complaints = False

    # ── 4. Dynamic Weight Re-Normalization ──
    active_weights = {}
    active_weights['task'] = w_c_raw
    if has_inspections:
        active_weights['inspection'] = w_i_raw
    if has_complaints:
        active_weights['complaint'] = w_k_raw

    sum_active = sum(active_weights.values())
    if sum_active > 0:
        normalized_weights = {k: (v / sum_active) for k, v in active_weights.items()}
    else:
        normalized_weights = {'task': 1.0}

    total_score = normalized_weights.get('task', 0.0) * t_score
    if has_inspections and i_score is not None:
        total_score += normalized_weights.get('inspection', 0.0) * i_score
    if has_complaints and c_score is not None:
        total_score += normalized_weights.get('complaint', 0.0) * c_score

    total_score_rounded = round(total_score, 2)

    return {
        "site_id": str(site.id),
        "site_name": site.name,
        "month": f"{year:04d}-{month:02d}",
        "total_score": total_score_rounded,
        "task_completion": {
            "score_pct": round(t_score, 2),
            "total_scheduled": total_tasks_count,
            "excused_skips": excused_count,
            "denominator": denominator_tasks,
            "completed_approved": base_tasks.filter(status='DONE', needs_review=False).count(),
            "unexcused_or_missed": denominator_tasks - base_tasks.filter(status='DONE', needs_review=False).count(),
            "weight_used": round(normalized_weights.get('task', 0.0) * 100, 1)
        },
        "inspection": {
            "score_pct": round(i_score, 2) if i_score is not None else None,
            "count": inspection_count,
            "weight_used": round(normalized_weights.get('inspection', 0.0) * 100, 1) if has_inspections else 0.0
        },
        "complaint_sla": {
            "score_pct": round(c_score, 2) if c_score is not None else None,
            "count": complaint_count,
            "weight_used": round(normalized_weights.get('complaint', 0.0) * 100, 1) if has_complaints else 0.0
        },
        "raw_weights_configured": {
            "completion": w_c_raw,
            "inspection": w_i_raw,
            "complaint": w_k_raw
        }
    }


def create_or_get_quality_score_snapshot(
    site: Site,
    year: int,
    month: int,
    user=None
) -> QualityScoreSnapshot:
    """
    Retrieves or generates an immutable QualityScoreSnapshot for a closed month.
    """
    month_str = f"{year:04d}-{month:02d}"
    existing = QualityScoreSnapshot.objects.filter(site=site, month=month_str).first()
    if existing:
        return existing

    calc = calculate_monthly_quality_score(site, year, month)
    snapshot = QualityScoreSnapshot.objects.create(
        society=site.society,
        site=site,
        month=month_str,
        score=Decimal(str(calc["total_score"])),
        task_completion_pct=Decimal(str(calc["task_completion"]["score_pct"])),
        inspection_pct=Decimal(str(calc["inspection"]["score_pct"])) if calc["inspection"]["score_pct"] is not None else None,
        complaint_sla_pct=Decimal(str(calc["complaint_sla"]["score_pct"])) if calc["complaint_sla"]["score_pct"] is not None else None,
        weights_used=calc["raw_weights_configured"],
        breakdown=calc,
        is_locked=True,
        locked_at=timezone.now()
    )
    return snapshot

