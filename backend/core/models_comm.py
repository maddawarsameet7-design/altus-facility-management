from django.db import models
from .users import User # Assuming User is in models.py or users.py
from .bookings import Booking # Assuming Booking is in models.py

class Complaint(models.Model):
    """
    Ticketing system for clients to raise issues with services or workers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey('core.Booking', on_delete=models.CASCADE, related_name='complaints', null=True, blank=True)
    client = models.ForeignKey('core.ClientProfile', on_delete=models.CASCADE, related_name='complaints')
    
    subject = models.CharField(max_length=255)
    description = models.TextField()
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_INVESTIGATION', 'In Investigation'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent')
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Notification(models.Model):
    """
    System-wide notifications for users (Real-time & Inbox).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Type allows UI to render different icons/links
    TYPE_CHOICES = [
        ('JOB_ASSIGNED', 'Job Assigned'),
        ('BOOKING_CONFIRMED', 'Booking Confirmed'),
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('COMPLAINT_UPDATE', 'Complaint Update')
    ]
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
