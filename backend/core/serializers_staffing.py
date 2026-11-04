import os
from rest_framework import serializers
from .models import (
    Post, Shift, RosterAssignment, DailyRoster, LeaveRecord,
    AttendanceEvent, Alert, AuditLog, WorkerProfile, Site, Society,
    ReplacementRequest, ReplacementOffer, Notification
)
from .staffing_utils import calculate_schedule_warnings


class PostSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.name', read_only=True)
    society_name = serializers.CharField(source='society.name', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'society', 'society_name', 'site', 'site_name',
            'name', 'category', 'billing_basis', 'client_rate',
            'is_active', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShiftSerializer(serializers.ModelSerializer):
    post_name = serializers.CharField(source='post.name', read_only=True)
    site_id = serializers.UUIDField(source='post.site_id', read_only=True)

    class Meta:
        model = Shift
        fields = [
            'id', 'society', 'post', 'post_name', 'site_id',
            'name', 'start_time', 'end_time', 'crosses_midnight',
            'days_of_week', 'required_headcount', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'crosses_midnight', 'created_at', 'updated_at']


class RosterAssignmentSerializer(serializers.ModelSerializer):
    worker_name = serializers.SerializerMethodField()
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    post_name = serializers.CharField(source='shift.post.name', read_only=True)
    warnings = serializers.SerializerMethodField()

    class Meta:
        model = RosterAssignment
        fields = [
            'id', 'society', 'worker', 'worker_name', 'shift', 'shift_name',
            'post_name', 'start_date', 'end_date', 'assignment_type',
            'status', 'warnings', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'warnings', 'created_by', 'created_at', 'updated_at']

    def get_worker_name(self, obj):
        return f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip() or obj.worker.user.username

    def get_warnings(self, obj):
        try:
            return calculate_schedule_warnings(obj.worker, obj)
        except Exception:
            return []


class WorkerRedactedSerializer(serializers.ModelSerializer):
    """
    Client-safe worker serializer: returns name and photo only.
    Strictly omits phone number, ID documents, rating, etc.
    """
    name = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = WorkerProfile
        fields = ['id', 'name', 'profile_photo']

    def get_name(self, obj):
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.username

    def get_profile_photo(self, obj):
        return obj.profile_photo.url if obj.profile_photo else None


class DailyRosterSerializer(serializers.ModelSerializer):
    post_id = serializers.UUIDField(source='post.id', read_only=True)
    post_name = serializers.CharField(source='post.name', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    worker_details = serializers.SerializerMethodField()
    has_attendance = serializers.SerializerMethodField()

    class Meta:
        model = DailyRoster
        fields = [
            'id', 'society', 'post', 'post_id', 'post_name', 'shift', 'shift_name',
            'date', 'slot_number', 'worker', 'worker_details', 'status',
            'covered_by', 'shift_start_at', 'shift_end_at', 'has_attendance',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'shift_start_at', 'shift_end_at', 'has_attendance', 'created_at', 'updated_at']

    def get_worker_details(self, obj):
        worker = obj.covered_by or obj.worker
        if not worker:
            return None
        # Chairman and Member see redacted details; ops/workers see basic fields
        return WorkerRedactedSerializer(worker).data

    def get_has_attendance(self, obj):
        return hasattr(obj, 'attendance_event')


class LeaveRecordSerializer(serializers.ModelSerializer):
    worker_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRecord
        fields = [
            'id', 'society', 'worker', 'worker_name', 'start_date', 'end_date',
            'leave_type', 'status', 'approved_by', 'reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'approved_by', 'created_at', 'updated_at']

    def get_worker_name(self, obj):
        return f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip() or obj.worker.user.username


class AttendanceEventSerializer(serializers.ModelSerializer):
    worker_name = serializers.SerializerMethodField()
    shift_name = serializers.CharField(source='roster_entry.shift.name', read_only=True)
    date = serializers.DateField(source='roster_entry.date', read_only=True)

    class Meta:
        model = AttendanceEvent
        fields = [
            'id', 'society', 'roster_entry', 'date', 'worker', 'worker_name',
            'shift_name', 'clock_in_uuid', 'clock_out_uuid', 'clock_in_at',
            'clock_out_at', 'client_timestamp', 'server_timestamp',
            'time_mismatch_flag', 'latitude', 'longitude', 'gps_accuracy_m',
            'distance_from_site_m', 'mock_location_flag', 'flags',
            'worked_minutes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'server_timestamp', 'time_mismatch_flag',
            'distance_from_site_m', 'flags', 'worked_minutes',
            'created_at', 'updated_at'
        ]

    def get_worker_name(self, obj):
        return f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip() or obj.worker.user.username


class AlertSerializer(serializers.ModelSerializer):
    post_name = serializers.CharField(source='roster_entry.post.name', read_only=True, default='')
    shift_name = serializers.CharField(source='roster_entry.shift.name', read_only=True, default='')
    date = serializers.DateField(source='roster_entry.date', read_only=True, default=None)

    class Meta:
        model = Alert
        fields = [
            'id', 'society', 'alert_type', 'roster_entry', 'date',
            'post_name', 'shift_name', 'status', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'society', 'actor', 'actor_username', 'action',
            'target_model', 'target_id', 'changes', 'reason', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReplacementOfferSerializer(serializers.ModelSerializer):
    worker_name = serializers.SerializerMethodField()
    post_name = serializers.CharField(source='request.roster_entry.post.name', read_only=True)
    shift_name = serializers.CharField(source='request.roster_entry.shift.name', read_only=True)
    shift_date = serializers.DateField(source='request.roster_entry.date', read_only=True)
    shift_start_at = serializers.DateTimeField(source='request.roster_entry.shift_start_at', read_only=True)
    shift_end_at = serializers.DateTimeField(source='request.roster_entry.shift_end_at', read_only=True)
    site_name = serializers.CharField(source='request.roster_entry.post.site.name', read_only=True)

    class Meta:
        model = ReplacementOffer
        fields = [
            'id', 'society', 'request', 'worker', 'worker_name',
            'site_name', 'post_name', 'shift_name', 'shift_date',
            'shift_start_at', 'shift_end_at', 'status', 'offered_at',
            'responded_at', 'expires_at', 'decline_reason', 'created_at'
        ]
        read_only_fields = ['id', 'society', 'status', 'offered_at', 'responded_at', 'created_at']

    def get_worker_name(self, obj):
        return f"{obj.worker.user.first_name} {obj.worker.user.last_name}".strip() or obj.worker.user.username


class ReplacementRequestSerializer(serializers.ModelSerializer):
    post_name = serializers.CharField(source='roster_entry.post.name', read_only=True)
    shift_name = serializers.CharField(source='roster_entry.shift.name', read_only=True)
    shift_date = serializers.DateField(source='roster_entry.date', read_only=True)
    shift_start_at = serializers.DateTimeField(source='roster_entry.shift_start_at', read_only=True)
    shift_end_at = serializers.DateTimeField(source='roster_entry.shift_end_at', read_only=True)
    site_name = serializers.CharField(source='roster_entry.post.site.name', read_only=True)
    filled_by_worker_name = serializers.SerializerMethodField()
    active_offers_count = serializers.SerializerMethodField()

    class Meta:
        model = ReplacementRequest
        fields = [
            'id', 'society', 'roster_entry', 'site_name', 'post_name',
            'shift_name', 'shift_date', 'shift_start_at', 'shift_end_at',
            'reason', 'status', 'opened_at', 'filled_at', 'filled_by_worker',
            'filled_by_worker_name', 'escalated_at', 'active_offers_count',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'opened_at', 'filled_at', 'filled_by_worker',
            'escalated_at', 'created_by', 'created_at', 'updated_at'
        ]

    def get_filled_by_worker_name(self, obj):
        if not obj.filled_by_worker:
            return None
        w = obj.filled_by_worker
        return f"{w.user.first_name} {w.user.last_name}".strip() or w.user.username

    def get_active_offers_count(self, obj):
        return obj.offers.filter(status='OFFERED').count()


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'society', 'recipient', 'notification_type',
            'title', 'body', 'related_model', 'related_id',
            'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'society', 'recipient', 'created_at']

