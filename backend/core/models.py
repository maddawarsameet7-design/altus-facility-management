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
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

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
