import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_CHOICES = [
        ('CLIENT', 'Client'),
        ('WORKER', 'Worker'),
        ('ADMIN', 'Admin')
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='CLIENT')
    
    # Resolving backwards relation clashes for custom users
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )


class ClientProfile(models.Model):
    """Profile for Organization Clients (Hospitals, Societies, etc)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    organization_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    
    ORG_TYPES = [
        ('HOSPITAL', 'Hospital'),
        ('SOCIETY', 'Housing Society'),
        ('OFFICE', 'Commercial Office')
    ]
    org_type = models.CharField(max_length=20, choices=ORG_TYPES)

    def __str__(self):
        return self.organization_name


class WorkerProfile(models.Model):
    """Profile for Service Providers (Electricians, Housekeeping, etc)"""
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
    """Types of services offered on the platform"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100) # e.g., Housekeeping, Security
    description = models.TextField()
    base_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name


class Booking(models.Model):
    """A service request from a client for a specific property"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='bookings')
    property = models.ForeignKey(Property, on_delete=models.CASCADE)
    service = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE)
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Assignment'),
        ('ASSIGNED', 'Worker Assigned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.service.name} at {self.property.name}"


class Assignment(models.Model):
    """Worker assigned to a specific booking"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='assignments')
    worker = models.ForeignKey(WorkerProfile, on_delete=models.CASCADE, related_name='assignments')
    
    STATUS_CHOICES = [
        ('PENDING_ACCEPTANCE', 'Pending Acceptance'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed')
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_ACCEPTANCE')
    assigned_at = models.DateTimeField(auto_now_add=True)

class Attendance(models.Model):
    """Digital attendance/time tracking for a shift"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE)
    clock_in = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    clock_in_lat = models.FloatField(null=True, blank=True)
    clock_in_lng = models.FloatField(null=True, blank=True)
    proof_of_work_url = models.URLField(max_length=500, null=True, blank=True)


class Review(models.Model):
    """Mutual review system for Clients and Workers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='reviews')
    
    # Reviewer and Reviewee can be Client or Worker
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received')
    
    rating = models.IntegerField() # 1-5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.reviewee.username} ({self.rating} stars)"
