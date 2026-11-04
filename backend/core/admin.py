from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, ClientProfile, WorkerProfile, Property,
    ServiceCategory, ServiceRequest, Assignment,
    Review, Attendance, ChatMessage, PaymentTransaction,
    Society, Site, Membership, SocietySettings, InviteCode,
    Post, Shift, RosterAssignment, DailyRoster, LeaveRecord,
    AttendanceEvent, Alert, AuditLog,
    ReplacementRequest, ReplacementOffer, Notification,
    OTPChallenge
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']


@admin.register(Society)
class SocietyAdmin(admin.ModelAdmin):
    list_display = ['name', 'client_type', 'is_active', 'created_at']
    list_filter = ['client_type', 'is_active']
    search_fields = ['name', 'billing_email']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Non-superuser staff: scope to their memberships
        return qs.filter(memberships__user=request.user, memberships__is_active=True)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'society', 'geofence_radius_m', 'is_active']
    list_filter = ['society', 'is_active']
    search_fields = ['name', 'society__name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(
            society__memberships__user=request.user,
            society__memberships__is_active=True
        )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'society', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'society']
    search_fields = ['user__username', 'society__name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(
            society__memberships__user=request.user,
            society__memberships__role='CHAIRMAN',
            society__memberships__is_active=True
        )


@admin.register(SocietySettings)
class SocietySettingsAdmin(admin.ModelAdmin):
    list_display = ['society', 'selfie_required', 'shift_start_grace_minutes', 'invoice_day']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(
            society__memberships__user=request.user,
            society__memberships__is_active=True
        )


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'society', 'role', 'use_count', 'max_uses', 'is_active', 'expires_at']
    list_filter = ['role', 'is_active', 'society']
    readonly_fields = ['code', 'use_count', 'created_at']


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
    list_display = ['id', 'reporter', 'category', 'society', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'society']
    search_fields = ['id', 'issue', 'reporter__username']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(
            society__memberships__user=request.user,
            society__memberships__is_active=True
        )


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
admin.site.register(Post)
admin.site.register(Shift)
admin.site.register(RosterAssignment)
admin.site.register(DailyRoster)
admin.site.register(LeaveRecord)
admin.site.register(AttendanceEvent)
admin.site.register(Alert)
admin.site.register(AuditLog)
admin.site.register(ReplacementRequest)
admin.site.register(ReplacementOffer)
admin.site.register(Notification)
admin.site.register(OTPChallenge)
