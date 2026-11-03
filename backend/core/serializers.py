from rest_framework import serializers
from django.utils import timezone
from .models import (
    User, ClientProfile, WorkerProfile, Property,
    ServiceCategory, ServiceRequest, Assignment,
    Attendance, Review, ChatMessage, PaymentTransaction, DeviceToken,
    Society, Site, Membership, SocietySettings, InviteCode,
)


class UserMembershipSerializer(serializers.ModelSerializer):
    society_name = serializers.ReadOnlyField(source='society.name')
    client_type = serializers.ReadOnlyField(source='society.client_type')

    class Meta:
        model = Membership
        fields = ['id', 'society', 'society_name', 'client_type', 'role', 'flat_or_unit', 'is_active']


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'memberships']
        read_only_fields = ['id', 'role']

    def get_memberships(self, obj):
        # Return user's memberships if user is saved in DB
        if not getattr(obj, 'pk', None):
            return []
        qs = obj.memberships.select_related('society').all()
        return UserMembershipSerializer(qs, many=True).data


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ['id', 'name', 'address', 'lat', 'lng']
        read_only_fields = ['id']


class ClientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    properties = PropertySerializer(many=True, read_only=True)

    class Meta:
        model = ClientProfile
        fields = ['id', 'user', 'organization_name', 'contact_person', 'phone', 'org_type', 'properties']
        read_only_fields = ['id']


class WorkerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkerProfile
        fields = ['id', 'user', 'phone', 'verification_status', 'average_rating', 'current_lat', 'current_lng']
        read_only_fields = ['id', 'verification_status', 'average_rating']


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    duration_hours = serializers.SerializerMethodField()
    service_name = serializers.ReadOnlyField(source='assignment.request.category.name')
    location = serializers.ReadOnlyField(source='assignment.request.location')
    society_name = serializers.ReadOnlyField(source='society.name')

    class Meta:
        model = Attendance
        fields = [
            'id', 'assignment', 'society', 'society_name',
            'service_name', 'location',
            'clock_in', 'clock_out', 'duration_hours',
            'proof_of_work_url', 'photo_proof'
        ]
        read_only_fields = ['id', 'society', 'society_name']

    def get_duration_hours(self, obj):
        if obj.clock_in and obj.clock_out:
            delta = obj.clock_out - obj.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return None


class AssignmentSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)
    attendance = AttendanceSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'worker', 'status', 'assigned_at', 'attendance']
        read_only_fields = ['id', 'assigned_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.ReadOnlyField(source='sender.username')

    class Meta:
        model = ChatMessage
        fields = ['id', 'request', 'sender', 'sender_name', 'content', 'timestamp']
        read_only_fields = ['id', 'sender', 'timestamp']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'request', 'transaction_id', 'amount', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class ServiceRequestSerializer(serializers.ModelSerializer):
    reporter = UserSerializer(read_only=True)
    category = ServiceCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)
    society_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    society_name = serializers.ReadOnlyField(source='society.name')
    assignments = AssignmentSerializer(many=True, read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    transaction = PaymentTransactionSerializer(read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'reporter', 'category', 'category_id',
            'society_id', 'society_name',
            'location', 'issue', 'status', 'priority',
            'scheduled_at', 'total_amount', 'is_paid',
            'created_at', 'updated_at', 'assignments',
            'messages', 'transaction'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status', 'is_paid']

    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        validated_data.pop('society_id', None)  # society is set by perform_create in mixin
        if category_id:
            validated_data['category'] = ServiceCategory.objects.get(id=category_id)
        return super().create(validated_data)


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'user', 'token', 'device_type', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


# ─── MULTI-TENANCY SERIALIZERS ────────────────────────────────────────────────

class SocietySerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Society
        fields = [
            'id', 'name', 'client_type', 'address',
            'gstin', 'billing_email', 'is_active', 'created_at',
            'member_count'
        ]
        read_only_fields = ['id', 'created_at']

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()


class SiteSerializer(serializers.ModelSerializer):
    society_name = serializers.ReadOnlyField(source='society.name')

    class Meta:
        model = Site
        fields = [
            'id', 'society', 'society_name', 'name',
            'latitude', 'longitude', 'geofence_radius_m', 'is_active'
        ]
        read_only_fields = ['id']


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    society_name = serializers.ReadOnlyField(source='society.name')

    class Meta:
        model = Membership
        fields = [
            'id', 'user', 'society', 'society_name',
            'role', 'flat_or_unit', 'is_active', 'joined_at'
        ]
        read_only_fields = ['id', 'joined_at']


class SocietySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocietySettings
        fields = [
            'society', 'selfie_required', 'shift_start_grace_minutes',
            'overtime_policy', 'invoice_day', 'payment_terms_days'
        ]


class InviteCodeSerializer(serializers.ModelSerializer):
    society_name = serializers.ReadOnlyField(source='society.name')
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = InviteCode
        fields = [
            'id', 'society', 'society_name', 'role', 'code',
            'expires_at', 'max_uses', 'use_count', 'is_active',
            'is_valid', 'created_at'
        ]
        read_only_fields = ['id', 'code', 'use_count', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.ReadOnlyField(source='reviewer.get_full_name')
    reviewee_name = serializers.ReadOnlyField(source='reviewee.get_full_name')

    class Meta:
        model = Review
        fields = [
            'id', 'request', 'reviewer', 'reviewer_name',
            'reviewee', 'reviewee_name', 'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'reviewer', 'created_at']
