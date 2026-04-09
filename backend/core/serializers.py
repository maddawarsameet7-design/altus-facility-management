from rest_framework import serializers
from .models import User, ClientProfile, WorkerProfile, Property, ServiceCategory, Booking, Assignment, Attendance, Review

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

class BookingSerializer(serializers.ModelSerializer):
    client = ClientProfileSerializer(read_only=True)
    client_id = serializers.UUIDField(write_only=True)
    
    property = PropertySerializer(read_only=True)
    property_id = serializers.UUIDField(write_only=True)
    
    service = ServiceCategorySerializer(read_only=True)
    service_id = serializers.UUIDField(write_only=True)
    
    assignments = AssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'client', 'client_id', 'property', 'property_id', 
            'service', 'service_id', 'status', 'scheduled_start', 
            'scheduled_end', 'total_amount', 'created_at', 'assignments'
        ]
        read_only_fields = ['id', 'created_at', 'status', 'total_amount']

    def create(self, validated_data):
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.ReadOnlyField(source='reviewer.get_full_name')
    reviewee_name = serializers.ReadOnlyField(source='reviewee.get_full_name')

    class Meta:
        model = Review
        fields = [
            'id', 'booking', 'reviewer', 'reviewer_name', 
            'reviewee', 'reviewee_name', 'rating', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
