import uuid
import random
import string
import secrets
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_CHOICES = [
        ('MEMBER', 'Society Member'),
        ('CHAIRMAN', 'Society Chairman'),
        ('WORKER', 'Facility Worker'),
        ('SUPERVISOR', 'Facility Supervisor'),
        ('DIRECTOR', 'Platform Director')
    ]
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='MEMBER')

    groups = models.ManyToManyField(
        'auth.Group', related_name='custom_user_set', blank=True,
        help_text='The groups this user belongs to.', verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', related_name='custom_user_set', blank=True,
        help_text='Specific permissions for this user.', verbose_name='user permissions',
    )


# ─── MULTI-TENANCY MODELS ────────────────────────────────────────────────────

class Society(models.Model):
    """
    Top-level tenant entity. A Society is a client of Altus —
    a housing society, hospital, or office that subscribes to facility services.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    CLIENT_TYPE_CHOICES = [
        ('SOCIETY', 'Housing Society'),
        ('HOSPITAL', 'Hospital / Healthcare'),
        ('OFFICE', 'Corporate / Office'),
    ]
    name = models.CharField(max_length=255)
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPE_CHOICES, default='SOCIETY')
    address = models.TextField()
    gstin = models.CharField(max_length=20, blank=True, null=True)
    billing_email = models.EmailField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Societies'
        ordering = ['name']

    def __str__(self):
        return self.name


class Site(models.Model):
    """
    A physical location within a Society (e.g. Building A, Block B Gate).
    Used for GPS geofencing on worker clock-in/out.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='sites')
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofence_radius_m = models.IntegerField(default=100)
    max_gps_accuracy_m = models.FloatField(default=50.0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def clean(self):
        super().clean()
        if self.max_gps_accuracy_m is not None and self.geofence_radius_m is not None:
            if self.max_gps_accuracy_m > self.geofence_radius_m:
                raise ValidationError({'max_gps_accuracy_m': 'GPS accuracy limit cannot exceed the geofence radius.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.society.name})"


class Membership(models.Model):
    """
    Links a User to a Society with a society-level role.
    A user may have memberships in multiple societies with different roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='memberships')
    ROLE_CHOICES = [
        ('MEMBER', 'Member'),
        ('CHAIRMAN', 'Chairman'),
        ('SUPERVISOR', 'Supervisor'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    flat_or_unit = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'society')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} @ {self.society.name} [{self.role}]"


class SocietySettings(models.Model):
    """Per-society operational configuration."""
    OVERTIME_CHOICES = [
        ('NONE', 'No Overtime Policy'),
        ('FLAT', 'Flat Overtime Rate'),
        ('MULTIPLIER', 'Multiplier-based Overtime'),
    ]
    society = models.OneToOneField(
        Society, on_delete=models.CASCADE,
        primary_key=True, related_name='settings'
    )
    selfie_required = models.BooleanField(default=False)
    shift_start_grace_minutes = models.IntegerField(default=15)
    overtime_policy = models.CharField(max_length=20, choices=OVERTIME_CHOICES, default='NONE')
    invoice_day = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(28)]
    )
    payment_terms_days = models.IntegerField(default=30)

    # ── Managed Staffing Operational Policies (No Hard-Coded Constants) ──
    MOCK_LOCATION_CHOICES = [
        ('REJECT', 'Reject Mock Location'),
        ('FLAG', 'Flag Mock Location'),
        ('ALLOW', 'Allow Mock Location'),
    ]
    mock_location_policy = models.CharField(max_length=20, choices=MOCK_LOCATION_CHOICES, default='REJECT')
    early_clock_in_minutes = models.IntegerField(default=30)
    early_leave_minutes = models.IntegerField(default=15)
    overtime_threshold_minutes = models.IntegerField(default=30)
    complaint_escalation_hours = models.IntegerField(default=24)

    class Meta:
        verbose_name_plural = 'Society Settings'

    def __str__(self):
        return f"Settings for {self.society.name}"


def _generate_invite_code():
    """Generate a cryptographically secure 16-character invite code like ALTUS-7X9B2K4M1P."""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(10))
    return f"ALTUS-{suffix}"


class InviteCode(models.Model):
    """
    One-time or limited-use invite codes for joining a Society.
    Created by a Director (any society) or a Chairman (their own society).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='invite_codes')
    ROLE_CHOICES = [
        ('MEMBER', 'Member'),
        ('CHAIRMAN', 'Chairman'),
        ('SUPERVISOR', 'Supervisor'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    code = models.CharField(max_length=30, unique=True, default=_generate_invite_code)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.IntegerField(default=1)
    use_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} → {self.society.name} [{self.role}]"

    @property
    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.use_count >= self.max_uses:
            return False
        return True


# ─── SECURE FILE UPLOAD HANDLERS ─────────────────────────────────────────────

def upload_worker_doc(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'pdf'
    return f'worker_docs/{uuid.uuid4().hex}/{uuid.uuid4().hex}.{ext}'


def upload_worker_photo(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    return f'worker_photos/{uuid.uuid4().hex}/{uuid.uuid4().hex}.{ext}'


def upload_attendance_proof(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    return f'attendance_proofs/{uuid.uuid4().hex}/{uuid.uuid4().hex}.{ext}'


def upload_selfie_path(instance, filename):
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    return f'selfies/{instance.society_id}/{uuid.uuid4().hex}.{ext}'


def get_private_storage_wrapper():
    from core.storage import get_private_storage
    return get_private_storage()


# ─── EXISTING MODELS ─────────────────────────────────────────────────────────

class ClientProfile(models.Model):
    """Legacy per-user org profile — kept for backward compat. New tenancy uses Society."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    organization_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    ORG_TYPES = [
        ('SOCIETY', 'Housing Society'),
        ('CORPORATE', 'Commercial Complex')
    ]
    org_type = models.CharField(max_length=20, choices=ORG_TYPES, default='SOCIETY')

    def __str__(self):
        return self.organization_name


class WorkerProfile(models.Model):
    """Profile for Service Providers. Workers are deployed to societies via roster — no direct society FK."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker_profile')
    phone = models.CharField(max_length=20)
    STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('SUSPENDED', 'Suspended')
    ]
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    id_document = models.FileField(upload_to=upload_worker_doc, null=True, blank=True)
    profile_photo = models.ImageField(upload_to=upload_worker_photo, null=True, blank=True)
    average_rating = models.FloatField(default=0.0)
    current_lat = models.FloatField(null=True, blank=True)
    current_lng = models.FloatField(null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"


class Property(models.Model):
    """Physical locations managed by Clients"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=255)
    address = models.TextField()
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.client.organization_name})"


class ServiceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    base_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ServiceRequest(models.Model):
    """A service request raised within a Society."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests_made')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE)

    # ── Society scoping ──
    society = models.ForeignKey(
        Society, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='service_requests'
    )

    location = models.CharField(max_length=255, help_text="e.g., Block A, Main Gate")
    issue = models.TextField(blank=True)
    STATUS_CHOICES = [
        ('Requested', 'Requested'),
        ('Investigating', 'Investigating'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Cancelled', 'Cancelled')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Requested')
    PRIORITY_CHOICES = [
        ('Normal', 'Normal'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical')
    ]
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='Normal')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        from core.middleware import get_current_user
        current_user = get_current_user()
        if current_user and current_user.is_authenticated:
            if getattr(current_user, 'role', '') != 'DIRECTOR' and not getattr(current_user, 'is_superuser', False):
                if not self.society_id:
                    raise ValidationError({'society': 'Society is required for non-Director users.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.name} - {self.location} ({self.status})"


class Assignment(models.Model):
    """Worker assigned to a specific service request"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='assignments')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='assignments')
    STATUS_CHOICES = [
        ('PENDING_ACCEPTANCE', 'Pending Acceptance'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed')
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_ACCEPTANCE')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_at']


class Attendance(models.Model):
    """Digital attendance/time tracking for a shift with direct Society linkage"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(
        Society, on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='attendances'
    )
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE)
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    proof_of_work_url = models.URLField(max_length=500, null=True, blank=True)
    photo_proof = models.ImageField(upload_to=upload_attendance_proof, null=True, blank=True)

    class Meta:
        ordering = ['-clock_in']

    def clean(self):
        super().clean()
        # Backfill society from assignment.request if missing
        if not self.society_id and self.assignment_id:
            try:
                self.society = self.assignment.request.society
            except Exception:
                pass
        from core.middleware import get_current_user
        current_user = get_current_user()
        if current_user and current_user.is_authenticated:
            if getattr(current_user, 'role', '') != 'DIRECTOR' and not getattr(current_user, 'is_superuser', False):
                if not self.society_id:
                    raise ValidationError({'society': 'Society is required for non-Director users.'})

    def save(self, *args, **kwargs):
        if not self.society_id and self.assignment_id:
            try:
                self.society = self.assignment.request.society
            except Exception:
                pass
        self.clean()
        super().save(*args, **kwargs)


class Review(models.Model):
    """Mutual review system for Members and Workers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.IntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review for {self.reviewee.username} ({self.rating} stars)"


class ChatMessage(models.Model):
    """Real-time messaging for each service request"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Msg from {self.sender.username} on {self.request.id}"


class PaymentTransaction(models.Model):
    """Tracks automated payments for services"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField(ServiceRequest, on_delete=models.CASCADE, related_name='transaction')
    transaction_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TX {self.transaction_id} - {self.status}"


class DeviceToken(models.Model):
    """Stores FCM device tokens for sending push notifications"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=20, choices=[('ios', 'iOS'), ('android', 'Android'), ('web', 'Web')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_type}"


# ─── MANAGED STAFFING FOUNDATION MODELS ──────────────────────────────────────

class Post(models.Model):
    """
    A staffed position at a client's Site (e.g. 'Block A Housekeeping', 'Gate 1 Night Guard').
    Direct society FK, scoped via SocietyScopedMixin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='posts')
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='posts')
    name = models.CharField(max_length=255)
    CATEGORY_CHOICES = [
        ('HOUSEKEEPING', 'Housekeeping'),
        ('SECURITY', 'Security'),
        ('MAINTENANCE', 'Maintenance'),
        ('OTHER', 'Other'),
    ]
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='HOUSEKEEPING')
    BILLING_BASIS_CHOICES = [
        ('FIXED_MONTHLY', 'Fixed Monthly'),
        ('PER_SHIFT', 'Per Shift'),
        ('PER_HOUR', 'Per Hour'),
    ]
    billing_basis = models.CharField(max_length=25, choices=BILLING_BASIS_CHOICES, default='PER_SHIFT')
    client_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['site', 'name']

    def clean(self):
        super().clean()
        if self.site_id and self.society_id:
            if self.site.society_id != self.society_id:
                raise ValidationError({'site': 'Site must belong to the same society as Post.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} @ {self.site.name}"


class Shift(models.Model):
    """
    Daily operating window for a Post. Supports overnight shifts crossing midnight.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='shifts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='shifts')
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    crosses_midnight = models.BooleanField(default=False)
    days_of_week = models.CharField(max_length=30, default='0,1,2,3,4,5,6')
    required_headcount = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['post', 'start_time']

    def clean(self):
        super().clean()
        if self.post_id and self.society_id:
            if self.post.society_id != self.society_id:
                raise ValidationError({'post': 'Post must belong to the same society as Shift.'})
        if self.start_time and self.end_time:
            self.crosses_midnight = self.end_time < self.start_time

    def save(self, *args, **kwargs):
        if self.start_time and self.end_time:
            self.crosses_midnight = self.end_time < self.start_time
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class RosterAssignment(models.Model):
    """
    Assignment of a worker to a shift.
    Cross-society overlap check ensures workers are never double-booked across any society.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='roster_assignments')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='roster_assignments')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='roster_assignments')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    ASSIGNMENT_TYPES = [
        ('REGULAR', 'Regular'),
        ('RELIEVER', 'Reliever'),
        ('TEMPORARY', 'Temporary'),
    ]
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES, default='REGULAR')
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ENDED', 'Ended'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_assignments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def clean(self):
        super().clean()
        if self.shift_id and self.society_id:
            if self.shift.society_id != self.society_id:
                raise ValidationError({'shift': 'Shift must belong to the same society as RosterAssignment.'})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})

        # Overlap check across ALL societies for this worker
        if self.status == 'ACTIVE' and self.worker_id and self.shift_id:
            from core.staffing_utils import dates_overlap, shifts_overlap
            active_existing = RosterAssignment.objects.filter(
                worker_id=self.worker_id,
                status='ACTIVE'
            ).exclude(pk=self.pk).select_related('shift')

            for existing in active_existing:
                if dates_overlap(self.start_date, self.end_date, existing.start_date, existing.end_date):
                    if shifts_overlap(self.shift, existing.shift):
                        raise ValidationError({
                            'worker': f"Worker already has an active assignment on shift '{existing.shift.name}' "
                                      f"with overlapping hours during this period."
                        })

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker.user.username} -> {self.shift.name} ({self.start_date})"


class DailyRoster(models.Model):
    """
    Daily slot requirement per (shift, date, slot_number).
    shift_start_at and shift_end_at are timezone-aware UTC datetimes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='daily_rosters')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='daily_rosters')
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='daily_rosters')
    date = models.DateField()
    slot_number = models.PositiveIntegerField(default=1)
    worker = models.ForeignKey(WorkerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='daily_roster_slots')
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('PRESENT', 'Present'),
        ('UNFILLED', 'Unfilled'),
        ('ABSENT', 'Absent'),
        ('COVERED', 'Covered'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    covered_by = models.ForeignKey(WorkerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='covering_roster_slots')
    shift_start_at = models.DateTimeField()
    shift_end_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['shift', 'date', 'slot_number'], name='unique_shift_date_slot')
        ]
        indexes = [
            models.Index(fields=['society', 'date']),
            models.Index(fields=['worker', 'date']),
            models.Index(fields=['post', 'date']),
        ]
        ordering = ['date', 'shift_start_at', 'slot_number']

    def clean(self):
        super().clean()
        if self.shift_id and self.society_id:
            if self.shift.society_id != self.society_id:
                raise ValidationError({'shift': 'Shift must belong to the same society as DailyRoster.'})
        if self.post_id and self.society_id:
            if self.post.society_id != self.society_id:
                raise ValidationError({'post': 'Post must belong to the same society as DailyRoster.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        worker_str = self.worker.user.username if self.worker else "UNFILLED"
        return f"{self.date} | {self.shift.name} slot #{self.slot_number} -> {worker_str} [{self.status}]"


class LeaveRecord(models.Model):
    """
    Worker leave records. Approving leave updates upcoming unfilled daily roster slots.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='leave_records')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='leave_records')
    start_date = models.DateField()
    end_date = models.DateField()
    LEAVE_TYPES = [
        ('WEEKLY_OFF', 'Weekly Off'),
        ('PAID_LEAVE', 'Paid Leave'),
        ('UNPAID_LEAVE', 'Unpaid Leave'),
        ('SICK', 'Sick Leave'),
    ]
    leave_type = models.CharField(max_length=25, choices=LEAVE_TYPES)
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_leaves')
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be earlier than start date.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker.user.username} {self.leave_type} ({self.start_date} to {self.end_date}) [{self.status}]"


class AttendanceEvent(models.Model):
    """
    Roster-based attendance record.
    OneToOneField with DailyRoster ensures exactly one attendance record per slot.
    UniqueConstraints on worker + clock_in_uuid and worker + clock_out_uuid prevent cross-worker leakage.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='attendance_events')
    roster_entry = models.OneToOneField(DailyRoster, on_delete=models.CASCADE, related_name='attendance_event')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='attendance_events')
    clock_in_uuid = models.UUIDField(null=True, blank=True)
    clock_out_uuid = models.UUIDField(null=True, blank=True)
    clock_in_at = models.DateTimeField(null=True, blank=True)
    clock_out_at = models.DateTimeField(null=True, blank=True)
    client_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)
    time_mismatch_flag = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_accuracy_m = models.FloatField(null=True, blank=True)
    distance_from_site_m = models.FloatField(null=True, blank=True)
    mock_location_flag = models.BooleanField(default=False)
    selfie_file = models.FileField(upload_to=upload_selfie_path, storage=get_private_storage_wrapper, null=True, blank=True)
    flags = models.CharField(max_length=100, blank=True)
    worked_minutes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['worker', 'clock_in_uuid'], name='unique_worker_clock_in_uuid'),
            models.UniqueConstraint(fields=['worker', 'clock_out_uuid'], name='unique_worker_clock_out_uuid'),
        ]
        indexes = [
            models.Index(fields=['society', 'clock_in_at']),
            models.Index(fields=['worker', 'clock_in_at']),
        ]
        ordering = ['-clock_in_at']

    def clean(self):
        super().clean()
        if self.roster_entry_id and self.society_id:
            if self.roster_entry.society_id != self.society_id:
                raise ValidationError({'roster_entry': 'Roster entry must belong to the same society as AttendanceEvent.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attendance {self.worker.user.username} @ {self.roster_entry.date} ({self.clock_in_at})"


class Alert(models.Model):
    """
    Staffing alert for unfilled slots, tardiness, or unexplained absences.
    UniqueConstraint per (roster_entry, alert_type) prevents duplicate alert storms.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='staffing_alerts')
    ALERT_TYPES = [
        ('ABSENT', 'Worker Absent'),
        ('LATE', 'Worker Late'),
        ('UNFILLED', 'Shift Unfilled'),
    ]
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    roster_entry = models.ForeignKey(DailyRoster, on_delete=models.CASCADE, related_name='alerts')
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('RESOLVED', 'Resolved'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['roster_entry', 'alert_type'], name='unique_roster_entry_alert_type')
        ]
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.roster_entry_id and self.society_id:
            if self.roster_entry.society_id != self.society_id:
                raise ValidationError({'roster_entry': 'Roster entry must belong to the same society as Alert.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Alert {self.alert_type} @ {self.roster_entry} [{self.status}]"


class AuditLog(models.Model):
    """
    Immutable audit trail for supervisory overrides and attendance corrections.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)
    target_model = models.CharField(max_length=50)
    target_id = models.UUIDField()
    changes = models.JSONField(default=dict)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor.username} {self.action} on {self.target_model}:{self.target_id}"
