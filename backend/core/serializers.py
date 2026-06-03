from rest_framework import serializers
from .models import (
    User, ClientProfile, WorkerProfile, Property, 
    ServiceCategory, ServiceRequest, Assignment, 
    Attendance, Review, ChatMessage, PaymentTransaction
)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
        read_only_fields = ['id', 'role']

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
    class Meta:
        model = Attendance
        fields = '__all__'

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
        read_only_fields = ['id', 'timestamp']


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ['id', 'request', 'transaction_id', 'amount', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']


class ServiceRequestSerializer(serializers.ModelSerializer):
    reporter = UserSerializer(read_only=True)
    
    category = ServiceCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)
    
    assignments = AssignmentSerializer(many=True, read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)
    transaction = PaymentTransactionSerializer(read_only=True)

    class Meta:
        model = ServiceRequest
        fields = [
            'id', 'reporter', 'category', 'category_id', 
            'location', 'issue', 'status', 'priority',
            'scheduled_at', 'total_amount', 'is_paid', 
            'created_at', 'updated_at', 'assignments',
            'messages', 'transaction'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'status', 'is_paid']

    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        if category_id:
            from .models import ServiceCategory
            validated_data['category'] = ServiceCategory.objects.get(id=category_id)
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.ReadOnlyField(source='reviewer.get_full_name')
    reviewee_name = serializers.ReadOnlyField(source='reviewee.get_full_name')

    class Meta:
        model = Review
        fields = [
            'id', 'request', 'reviewer', 'reviewer_name', 
            'reviewee', 'reviewee_name', 'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
