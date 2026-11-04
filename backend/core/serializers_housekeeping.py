from decimal import Decimal
from rest_framework import serializers
from core.models import (
    Area, TaskTemplate, TaskInstance, TaskPhoto,
    Inspection, InspectionPhoto, Complaint,
    SupplyItem, SupplyRequest, QualityScoreSnapshot,
    WorkerProfile, User
)


class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Area
        fields = ['id', 'society', 'site', 'name', 'floor_or_block', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaskTemplateSerializer(serializers.ModelSerializer):
    post_name = serializers.CharField(source='post.name', read_only=True)
    area_name = serializers.CharField(source='area.name', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)

    class Meta:
        model = TaskTemplate
        fields = [
            'id', 'society', 'post', 'post_name', 'area', 'area_name',
            'shift', 'shift_name', 'name', 'frequency', 'days_of_week',
            'day_of_month', 'photo_required', 'estimated_minutes',
            'sort_order', 'is_active', 'effective_from', 'effective_to',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaskPhotoSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.user.get_full_name', read_only=True)

    class Meta:
        model = TaskPhoto
        fields = [
            'id', 'task_instance', 'kind', 'file_url', 'thumbnail_url',
            'client_uuid', 'captured_at', 'server_received_at',
            'gps_latitude', 'gps_longitude', 'gps_accuracy_m',
            'distance_from_site_m', 'flags', 'uploaded_by', 'uploaded_by_name',
            'created_at'
        ]
        read_only_fields = ['id', 'server_received_at', 'created_at', 'distance_from_site_m', 'flags']

    def get_file_url(self, obj):
        return f"/api/housekeeping/photos/{obj.id}/file/"

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return f"/api/housekeeping/photos/{obj.id}/file/?thumb=1"
        return f"/api/housekeeping/photos/{obj.id}/file/"


class TaskInstanceSerializer(serializers.ModelSerializer):
    area_name = serializers.CharField(source='area.name', read_only=True)
    floor_or_block = serializers.CharField(source='area.floor_or_block', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    post_name = serializers.CharField(source='post.name', read_only=True)
    claimed_by_name = serializers.CharField(source='claimed_by.user.get_full_name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.user.get_full_name', read_only=True)
    photos = TaskPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = TaskInstance
        fields = [
            'id', 'society', 'template', 'post', 'post_name', 'shift', 'shift_name',
            'area', 'area_name', 'floor_or_block', 'name', 'photo_required',
            'estimated_minutes', 'due_date', 'shift_start_at', 'shift_end_at',
            'status', 'expected_photo_uuids', 'evidence_deadline',
            'claimed_by', 'claimed_by_name', 'completed_by', 'completed_by_name',
            'started_at', 'completed_at', 'skip_reason', 'is_excused',
            'excuse_reason', 'notes', 'is_rework', 'needs_review',
            'reviewed_by', 'reviewed_at', 'photos', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'society', 'template', 'post', 'shift', 'area',
            'due_date', 'shift_start_at', 'shift_end_at', 'created_at', 'updated_at'
        ]


class InspectionPhotoSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = InspectionPhoto
        fields = ['id', 'inspection', 'file_url', 'caption', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_file_url(self, obj):
        return f"/api/housekeeping/inspections/{obj.inspection_id}/photos/{obj.id}/"


class InspectionSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    post_name = serializers.CharField(source='post.name', read_only=True)
    area_name = serializers.CharField(source='area.name', read_only=True)
    photos = InspectionPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Inspection
        fields = [
            'id', 'society', 'post', 'post_name', 'area', 'area_name',
            'inspector', 'inspector_name', 'date', 'score', 'notes',
            'status', 'shared_with_client', 'photos', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'inspector', 'created_at', 'updated_at']


class ComplaintSerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source='raised_by.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    site_name = serializers.CharField(source='site.name', read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            'id', 'society', 'site', 'site_name', 'post', 'area',
            'raised_by', 'raised_by_name', 'description', 'photo_url',
            'status', 'assigned_to', 'assigned_to_name', 'resolution_notes',
            'resolved_at', 'client_confirmed', 'reopened_count',
            'rejection_reason', 'disputed_by_client', 'dispute_notes',
            'escalated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'raised_by', 'reopened_count', 'escalated_at',
            'created_at', 'updated_at'
        ]

    def get_photo_url(self, obj):
        if obj.photo:
            return f"/api/housekeeping/complaints/{obj.id}/photo/"
        return None


class SupplyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplyItem
        fields = ['id', 'society', 'name', 'category', 'unit', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SupplyRequestSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_unit = serializers.CharField(source='item.unit', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.user.get_full_name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)

    class Meta:
        model = SupplyRequest
        fields = [
            'id', 'society', 'item', 'item_name', 'item_unit', 'quantity',
            'requested_by', 'requested_by_name', 'status', 'reviewed_by',
            'reviewed_by_name', 'reviewed_at', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'requested_by', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at']


class QualityScoreSnapshotSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source='site.name', read_only=True)

    class Meta:
        model = QualityScoreSnapshot
        fields = [
            'id', 'society', 'site', 'site_name', 'month', 'score',
            'task_completion_pct', 'inspection_pct', 'complaint_sla_pct',
            'weights_used', 'breakdown', 'locked_at', 'is_locked',
            'corrected_at', 'correction_notes', 'corrected_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'locked_at', 'is_locked', 'created_at', 'updated_at']
