import uuid
import random
import string
import secrets
from decimal import Decimal
from django.db import models
from django.utils import timezone
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
    pincode = models.CharField(max_length=10, blank=True, null=True)
    area_name = models.CharField(max_length=100, blank=True, null=True)
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
    replacement_offer_expiry_minutes = models.IntegerField(default=15)
    replacement_escalation_minutes = models.IntegerField(default=60)
    min_rest_gap_hours = models.IntegerField(default=8)

    # ── Housekeeping Operational Policies & Quality Weights ──
    task_missed_grace_minutes = models.IntegerField(default=30)
    max_photos_per_task = models.IntegerField(default=6)
    PHOTO_GEOFENCE_POLICY_CHOICES = [
        ('REJECT', 'Reject Photos Outside Geofence'),
        ('FLAG', 'Flag Photos Outside Geofence for Review'),
    ]
    photo_geofence_policy = models.CharField(max_length=10, choices=PHOTO_GEOFENCE_POLICY_CHOICES, default='REJECT')
    evidence_deadline_hours = models.IntegerField(default=24)
    photo_retention_days = models.IntegerField(default=90)
    completion_weight = models.IntegerField(default=40)
    inspection_weight = models.IntegerField(default=40)
    complaint_weight = models.IntegerField(default=20)

    class Meta:
        verbose_name_plural = 'Society Settings'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(completion_weight__gte=0) &
                          models.Q(inspection_weight__gte=0) &
                          models.Q(complaint_weight__gte=0),
                name='society_settings_weights_gte_zero'
            )
        ]

    def clean(self):
        super().clean()
        w_c = self.completion_weight if self.completion_weight is not None else 40
        w_i = self.inspection_weight if self.inspection_weight is not None else 40
        w_k = self.complaint_weight if self.complaint_weight is not None else 20
        if w_c + w_i + w_k != 100:
            raise ValidationError("Quality score weights (completion, inspection, complaint) must sum to exactly 100.")
        if min(w_c, w_i, w_k) < 0:
            raise ValidationError("Quality score weights must be non-negative.")

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
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
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
    home_pincode = models.CharField(max_length=10, blank=True, null=True)
    home_area = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=30, default='HOUSEKEEPING')
    device_id = models.CharField(max_length=100, blank=True, null=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    sessions_revoked_at = models.DateTimeField(null=True, blank=True)
    new_device_approved = models.BooleanField(default=True)
    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    bank_ifsc = models.CharField(max_length=20, blank=True, null=True)
    compensation_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        if self.phone:
            from core.otp_utils import normalize_phone
            norm = normalize_phone(self.phone)
            self.phone = norm if norm else None
        elif self.phone == '':
            self.phone = None
        super().save(*args, **kwargs)

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
        ('REWORK_NO_SHIFT', 'Rework Has No Scheduled Shift'),
    ]
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    roster_entry = models.ForeignKey(DailyRoster, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
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


# ─── REPLACEMENT WORKFLOW MODELS ─────────────────────────────────────────────

class ReplacementRequest(models.Model):
    """
    Staffing replacement request opened when a scheduled worker is absent,
    on leave, or when a slot is unfilled.
    Enforces that only one active replacement request exists per DailyRoster slot at DB level.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='replacement_requests')
    roster_entry = models.ForeignKey(DailyRoster, on_delete=models.CASCADE, related_name='replacement_requests')
    REASON_CHOICES = [
        ('ABSENT', 'Worker Absent'),
        ('LEAVE', 'Approved Leave'),
        ('UNFILLED', 'Unfilled Slot'),
        ('MANUAL', 'Manual Request'),
    ]
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='UNFILLED')
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('OFFERING', 'Offers Dispatched'),
        ('FILLED', 'Filled'),
        ('ESCALATED', 'Escalated'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    opened_at = models.DateTimeField(auto_now_add=True)
    filled_at = models.DateTimeField(null=True, blank=True)
    filled_by_worker = models.ForeignKey(WorkerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='filled_replacements')
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_replacements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['roster_entry'],
                condition=models.Q(status__in=['OPEN', 'OFFERING', 'ESCALATED']),
                name='unique_active_replacement_per_slot'
            )
        ]
        indexes = [
            models.Index(fields=['society', 'status']),
            models.Index(fields=['roster_entry', 'status']),
        ]
        ordering = ['-opened_at']

    def clean(self):
        super().clean()
        if self.roster_entry_id and self.society_id:
            if self.roster_entry.society_id != self.society_id:
                raise ValidationError({'roster_entry': 'Roster entry must belong to the same society as ReplacementRequest.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Replacement for {self.roster_entry} [{self.status}]"


class ReplacementOffer(models.Model):
    """
    An offer dispatched to a reliever worker for an open replacement request.
    DB constraint enforces only one ACCEPTED offer per request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='replacement_offers')
    request = models.ForeignKey(ReplacementRequest, on_delete=models.CASCADE, related_name='offers')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='replacement_offers')
    STATUS_CHOICES = [
        ('OFFERED', 'Offered'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
        ('EXPIRED', 'Expired'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFERED')
    offered_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    decline_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['request'],
                condition=models.Q(status='ACCEPTED'),
                name='unique_accepted_offer_per_request'
            ),
            models.UniqueConstraint(
                fields=['request', 'worker'],
                name='unique_offer_per_request_worker'
            )
        ]
        indexes = [
            models.Index(fields=['society', 'status']),
            models.Index(fields=['worker', 'status']),
        ]
        ordering = ['-offered_at']

    def clean(self):
        super().clean()
        if self.request_id and self.society_id:
            if self.request.society_id != self.society_id:
                raise ValidationError({'request': 'Request must belong to the same society as ReplacementOffer.'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Offer to {self.worker.user.username} for Request {self.request_id} [{self.status}]"


class Notification(models.Model):
    """
    In-app notifications for workers and supervisors.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    body = models.TextField()
    related_model = models.CharField(max_length=50, blank=True)
    related_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['recipient', 'read_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"


# ─── WORKER OTP AUTHENTICATION MODELS ────────────────────────────────────────

class OTPChallenge(models.Model):
    """
    Challenge record for worker OTP login.
    Enforces HMAC code hashing, anti-enumeration, attempt lockout, and single atomic consumption.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=128)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_id = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['phone', 'created_at']),
            models.Index(fields=['phone', 'consumed_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"OTPChallenge for {self.phone} [{self.created_at}]"


# ─── HOUSEKEEPING TASK MANAGEMENT MODELS ─────────────────────────────────────

def task_photo_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    return f"housekeeping/tasks/{instance.society_id}/{uuid.uuid4()}{ext}"


def task_thumbnail_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    return f"housekeeping/thumbnails/{instance.society_id}/{uuid.uuid4()}{ext}"


def inspection_photo_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    return f"housekeeping/inspections/{instance.society_id}/{uuid.uuid4()}{ext}"


def complaint_photo_upload_path(instance, filename):
    import os, uuid
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    return f"housekeeping/complaints/{instance.society_id}/{uuid.uuid4()}{ext}"


class Area(models.Model):
    """
    Physical area or zone within a Site (e.g. Lobby, Stairs, Lift, Washroom, Garden).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='areas')
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='areas')
    name = models.CharField(max_length=100)
    floor_or_block = models.CharField(max_length=50, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'name', 'floor_or_block'], name='unique_site_area_block')
        ]
        ordering = ['name', 'floor_or_block']

    def clean(self):
        super().clean()
        if self.site_id and self.society_id:
            if self.site.society_id != self.society_id:
                raise ValidationError({'site': 'Site must belong to the same society as Area.'})

    def __str__(self):
        loc = f" ({self.floor_or_block})" if self.floor_or_block else ""
        return f"{self.name}{loc} @ {self.site.name}"


class TaskTemplate(models.Model):
    """
    Defines a recurring housekeeping task assigned to a post, area, and shift.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='task_templates')
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name='task_templates')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='task_templates')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='task_templates')
    name = models.CharField(max_length=150)
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ]
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='DAILY')
    days_of_week = models.JSONField(default=list, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(31)])
    PHOTO_REQ_CHOICES = [
        ('NONE', 'None'),
        ('BEFORE_AFTER', 'Before & After'),
        ('AFTER_ONLY', 'After Only'),
    ]
    photo_required = models.CharField(max_length=20, choices=PHOTO_REQ_CHOICES, default='NONE')
    estimated_minutes = models.IntegerField(default=30)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def clean(self):
        super().clean()
        if self.post_id and self.society_id and self.post.society_id != self.society_id:
            raise ValidationError({'post': 'Post must belong to the same society as TaskTemplate.'})
        if self.area_id and self.society_id and self.area.society_id != self.society_id:
            raise ValidationError({'area': 'Area must belong to the same society as TaskTemplate.'})
        if self.shift_id and self.society_id and self.shift.society_id != self.society_id:
            raise ValidationError({'shift': 'Shift must belong to the same society as TaskTemplate.'})
        if self.shift_id and self.post_id and self.shift.post_id != self.post_id:
            raise ValidationError({'shift': 'Shift must belong to the selected Post.'})
        if self.area_id and self.post_id and self.area.site_id != self.post.site_id:
            raise ValidationError({'area': 'Area must belong to the same Site as Post.'})
        if self.frequency == 'WEEKLY' and not self.days_of_week:
            raise ValidationError({'days_of_week': 'Weekly templates must specify operating days_of_week.'})
        if self.frequency == 'MONTHLY' and not self.day_of_month:
            raise ValidationError({'day_of_month': 'Monthly templates must specify day_of_month.'})

    def __str__(self):
        return f"{self.name} ({self.area.name} / {self.shift.name})"


class TaskInstance(models.Model):
    """
    Generated concrete task for a specific date and shift.
    Belongs to the post and shift (not permanently bound to one worker).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='task_instances')
    template = models.ForeignKey(TaskTemplate, on_delete=models.PROTECT, null=True, blank=True, related_name='instances')
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name='task_instances')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='task_instances')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name='task_instances')
    name = models.CharField(max_length=150)
    photo_required = models.CharField(max_length=20, default='NONE')
    estimated_minutes = models.IntegerField(default=30)
    due_date = models.DateField(db_index=True)
    shift_start_at = models.DateTimeField()
    shift_end_at = models.DateTimeField()
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('AWAITING_EVIDENCE', 'Awaiting Evidence'),
        ('DONE', 'Done'),
        ('SKIPPED', 'Skipped'),
        ('MISSED', 'Missed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    expected_photo_uuids = models.JSONField(default=list, blank=True)
    evidence_deadline = models.DateTimeField(null=True, blank=True)
    claimed_by = models.ForeignKey(WorkerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='claimed_tasks')
    completed_by = models.ForeignKey(WorkerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_tasks')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    SKIP_REASON_CHOICES = [
        ('AREA_LOCKED', 'Area Locked'),
        ('RESIDENT_REQUEST', 'Resident Request'),
        ('NO_SUPPLIES', 'No Supplies Available'),
        ('EXCUSED', 'Excused by Supervisor'),
        ('OTHER', 'Other Reason'),
    ]
    skip_reason = models.CharField(max_length=30, blank=True, null=True, choices=SKIP_REASON_CHOICES)
    is_excused = models.BooleanField(default=False)
    excused_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='excused_tasks')
    excuse_reason = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    is_rework = models.BooleanField(default=False)
    needs_review = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_tasks')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'due_date'],
                condition=models.Q(is_rework=False) & models.Q(template__isnull=False),
                name='unique_task_template_due_date'
            )
        ]
        indexes = [
            models.Index(fields=['society', 'due_date']),
            models.Index(fields=['post', 'due_date']),
            models.Index(fields=['claimed_by', 'due_date']),
            models.Index(fields=['status', 'shift_end_at']),
        ]
        ordering = ['due_date', 'shift_start_at', 'id']

    def clean(self):
        super().clean()
        if self.post_id and self.society_id and self.post.society_id != self.society_id:
            raise ValidationError({'post': 'Post must belong to the same society as TaskInstance.'})
        if self.shift_id and self.society_id and self.shift.society_id != self.society_id:
            raise ValidationError({'shift': 'Shift must belong to the same society as TaskInstance.'})
        if self.area_id and self.society_id and self.area.society_id != self.society_id:
            raise ValidationError({'area': 'Area must belong to the same society as TaskInstance.'})
        if self.shift_id and self.post_id and self.shift.post_id != self.post_id:
            raise ValidationError({'shift': 'Shift must belong to the selected Post.'})
        if self.area_id and self.post_id and self.area.site_id != self.post.site_id:
            raise ValidationError({'area': 'Area must belong to the same Site as Post.'})
        if self.template_id and self.template.society_id != self.society_id:
            raise ValidationError({'template': 'Template must belong to the same society as TaskInstance.'})

    def __str__(self):
        return f"{self.name} on {self.due_date} ({self.status})"


class TaskPhoto(models.Model):
    """
    Evidence photo captured for a task instance with capture-time GPS coordinates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='task_photos')
    task_instance = models.ForeignKey(TaskInstance, on_delete=models.PROTECT, related_name='photos')
    KIND_CHOICES = [
        ('BEFORE', 'Before Cleaning'),
        ('AFTER', 'After Cleaning'),
    ]
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    file = models.FileField(upload_to=task_photo_upload_path, storage=get_private_storage_wrapper)
    thumbnail = models.FileField(upload_to=task_thumbnail_upload_path, storage=get_private_storage_wrapper, null=True, blank=True)
    client_uuid = models.UUIDField(db_index=True)
    captured_at = models.DateTimeField()
    server_received_at = models.DateTimeField(auto_now_add=True)
    gps_latitude = models.FloatField(null=True, blank=True)
    gps_longitude = models.FloatField(null=True, blank=True)
    gps_accuracy_m = models.FloatField(null=True, blank=True)
    distance_from_site_m = models.FloatField(null=True, blank=True)
    flags = models.JSONField(default=list, blank=True)
    uploaded_by = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name='task_photos')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['client_uuid', 'uploaded_by'], name='unique_task_photo_client_uploader')
        ]
        ordering = ['captured_at']

    def clean(self):
        super().clean()
        if self.task_instance_id and self.society_id and self.task_instance.society_id != self.society_id:
            raise ValidationError({'task_instance': 'TaskInstance must belong to the same society as TaskPhoto.'})

    def __str__(self):
        return f"{self.kind} photo for {self.task_instance.name} ({self.client_uuid})"


class Inspection(models.Model):
    """
    Quality inspection performed by a Supervisor or Director.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='inspections')
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name='inspections')
    area = models.ForeignKey(Area, on_delete=models.PROTECT, null=True, blank=True, related_name='inspections')
    inspector = models.ForeignKey(User, on_delete=models.PROTECT, related_name='inspections_conducted')
    date = models.DateField(default=timezone.localdate)
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    STATUS_CHOICES = [
        ('PASSED', 'Passed (Score 4-5)'),
        ('NEEDS_REWORK', 'Needs Rework (Score 2-3)'),
        ('FAILED', 'Failed (Score 1)'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    shared_with_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def clean(self):
        super().clean()
        if self.post_id and self.society_id and self.post.society_id != self.society_id:
            raise ValidationError({'post': 'Post must belong to the same society as Inspection.'})
        if self.area_id and self.society_id and self.area.society_id != self.society_id:
            raise ValidationError({'area': 'Area must belong to the same society as Inspection.'})
        if self.inspector_id:
            role = getattr(self.inspector, 'role', '')
            if role not in ('SUPERVISOR', 'DIRECTOR'):
                raise ValidationError({'inspector': 'Inspector must have role SUPERVISOR or DIRECTOR.'})
            if role == 'SUPERVISOR' and self.society_id:
                has_mem = Membership.objects.filter(user=self.inspector, society_id=self.society_id, is_active=True).exists()
                if not has_mem:
                    raise ValidationError({'inspector': 'Supervisor must have active membership in this society.'})

    def __str__(self):
        return f"Inspection {self.score}/5 @ {self.post.name} by {self.inspector.username} ({self.date})"


class InspectionPhoto(models.Model):
    """
    Evidence photo attached to an inspection.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='inspection_photos')
    inspection = models.ForeignKey(Inspection, on_delete=models.PROTECT, related_name='photos')
    file = models.FileField(upload_to=inspection_photo_upload_path, storage=get_private_storage_wrapper)
    caption = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.inspection_id and self.society_id and self.inspection.society_id != self.society_id:
            raise ValidationError({'inspection': 'Inspection must belong to the same society.'})

    def __str__(self):
        return f"InspectionPhoto for {self.inspection_id}"


class Complaint(models.Model):
    """
    Housekeeping complaint raised by a society Member or Chairman.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='complaints')
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='complaints')
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints')
    raised_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='complaints_raised')
    description = models.TextField()
    photo = models.FileField(upload_to=complaint_photo_upload_path, storage=get_private_storage_wrapper, null=True, blank=True)
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('ACKNOWLEDGED', 'Acknowledged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN', db_index=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints_assigned')
    resolution_notes = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    client_confirmed = models.BooleanField(null=True, blank=True)
    reopened_count = models.IntegerField(default=0)
    rejection_reason = models.TextField(blank=True, default='')
    disputed_by_client = models.BooleanField(default=False)
    dispute_notes = models.TextField(blank=True, default='')
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.site_id and self.society_id and self.site.society_id != self.society_id:
            raise ValidationError({'site': 'Site must belong to the same society as Complaint.'})
        if self.post_id and self.society_id and self.post.society_id != self.society_id:
            raise ValidationError({'post': 'Post must belong to the same society as Complaint.'})
        if self.area_id and self.society_id and self.area.society_id != self.society_id:
            raise ValidationError({'area': 'Area must belong to the same society as Complaint.'})
        if self.raised_by_id and self.society_id:
            role = getattr(self.raised_by, 'role', '')
            if role != 'DIRECTOR':
                has_mem = Membership.objects.filter(user=self.raised_by, society_id=self.society_id, is_active=True).exists()
                if not has_mem:
                    raise ValidationError({'raised_by': 'User raising complaint must have an active membership in this society.'})
        if self.assigned_to_id and self.society_id:
            role = getattr(self.assigned_to, 'role', '')
            if role not in ('SUPERVISOR', 'DIRECTOR'):
                raise ValidationError({'assigned_to': 'Assignee must be a Supervisor or Director.'})
            if role == 'SUPERVISOR':
                has_mem = Membership.objects.filter(user=self.assigned_to, society_id=self.society_id, is_active=True).exists()
                if not has_mem:
                    raise ValidationError({'assigned_to': 'Supervisor must have an active membership in this society.'})

    def __str__(self):
        return f"Complaint #{str(self.id)[:8]} ({self.status}) @ {self.site.name}"


class SupplyItem(models.Model):
    """
    Inventory item stocked for housekeeping (e.g. chemicals, mop heads, garbage bags).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='supply_items')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, blank=True, default='Cleaning Supplies')
    unit = models.CharField(max_length=20, default='pcs')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['society', 'name'], name='unique_society_supply_item')
        ]
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.unit}) [{self.society.name}]"


class SupplyRequest(models.Model):
    """
    Supply request submitted by a worker and approved/issued by a supervisor.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='supply_requests')
    item = models.ForeignKey(SupplyItem, on_delete=models.PROTECT, related_name='requests')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    requested_by = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name='supply_requests')
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('ISSUED', 'Issued'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED', db_index=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_supply_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        super().clean()
        if self.item_id and self.society_id and self.item.society_id != self.society_id:
            raise ValidationError({'item': 'SupplyItem must belong to the same society.'})
        if self.reviewed_by_id:
            role = getattr(self.reviewed_by, 'role', '')
            if role not in ('SUPERVISOR', 'DIRECTOR'):
                raise ValidationError({'reviewed_by': 'Reviewer must have role SUPERVISOR or DIRECTOR.'})

    def __str__(self):
        return f"SupplyRequest {self.quantity} {self.item.name} ({self.status})"


class QualityScoreSnapshot(models.Model):
    """
    Immutable monthly quality score snapshot for client billing & SLA verification.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    society = models.ForeignKey(Society, on_delete=models.CASCADE, related_name='quality_snapshots')
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='quality_snapshots')
    month = models.CharField(max_length=7, db_index=True)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    task_completion_pct = models.DecimalField(max_digits=5, decimal_places=2)
    inspection_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    complaint_sla_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weights_used = models.JSONField(default=dict)
    breakdown = models.JSONField(default=dict)
    locked_at = models.DateTimeField(default=timezone.now)
    is_locked = models.BooleanField(default=True)
    corrected_at = models.DateTimeField(null=True, blank=True)
    correction_notes = models.TextField(blank=True, default='')
    corrected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['site', 'month'], name='unique_site_month_quality_snapshot')
        ]
        ordering = ['-month']

    def clean(self):
        super().clean()
        if self.site_id and self.society_id and self.site.society_id != self.society_id:
            raise ValidationError({'site': 'Site must belong to the same society.'})
        if self.pk:
            orig = QualityScoreSnapshot.objects.filter(pk=self.pk).first()
            if orig and orig.is_locked and not self.corrected_at and (orig.score != self.score or orig.breakdown != self.breakdown):
                raise ValidationError("Locked QualityScoreSnapshot cannot be modified directly without an audited correction.")

    def delete(self, *args, **kwargs):
        if self.is_locked:
            raise ValidationError("Locked QualityScoreSnapshot cannot be deleted.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"QualityScore {self.score}% for {self.site.name} ({self.month})"

