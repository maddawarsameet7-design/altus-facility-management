from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, ClientProfile, WorkerProfile, Property, 
    ServiceCategory, ServiceRequest, Assignment, 
    Review, Attendance, ChatMessage, PaymentTransaction
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']

@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'org_type', 'contact_person']

@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'verification_status']

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_hourly_rate']

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'reporter', 'category', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category']
    search_fields = ['id', 'issue', 'reporter__username']

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['request', 'worker', 'assigned_at']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'reviewee', 'rating']

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['request', 'sender', 'content', 'timestamp']
    list_filter = ['timestamp']

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'request', 'amount', 'status', 'created_at']
    list_filter = ['status']

admin.site.register(Property)
admin.site.register(Attendance)
