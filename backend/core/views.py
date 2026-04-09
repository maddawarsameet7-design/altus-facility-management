from django.db import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import ClientProfile, WorkerProfile, Property, ServiceCategory, Booking, Assignment, Review
from .serializers import (
    ClientProfileSerializer, WorkerProfileSerializer, 
    PropertySerializer, ServiceCategorySerializer, BookingSerializer, 
    AssignmentSerializer, ReviewSerializer
)

class ClientProfileViewSet(viewsets.ModelViewSet):
    """
    API for Managing Organization Profiles. 
    Restricted so clients can only see/edit their own profile.
    """
    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Admin can see all, Clients can see their own
        if getattr(self.request.user, 'role', '') == 'ADMIN':
            return ClientProfile.objects.all()
        return ClientProfile.objects.filter(user=self.request.user)

class WorkerViewSet(viewsets.ModelViewSet):
    """
    API for clients or admins to view available workers.
    Includes location tracking simulation logic.
    """
    queryset = WorkerProfile.objects.filter(verification_status='VERIFIED')
    serializer_class = WorkerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def live_location(self, request, pk=None):
        """
        Simulates real-time location tracking for a worker on a job.
        For demo: Returns the current coords if on an active job.
        """
        worker = self.get_object()
        # In a real app, this would pull from a Redis cache or real-time stream
        return Response({
            "worker_id": worker.id,
            "lat": worker.current_lat,
            "lng": worker.current_lng,
            "last_updated": worker.last_location_update
        })

class PropertyViewSet(viewsets.ModelViewSet):
    """
    API for managing properties owned by a client.
    """
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', '') == 'ADMIN':
            return Property.objects.all()
        return Property.objects.filter(client__user=user)

    def perform_create(self, serializer):
        client_profile = get_object_or_404(ClientProfile, user=self.request.user)
        serializer.save(client=client_profile)

class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Publicly accessible list of services offered by the platform.
    """
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [permissions.AllowAny]


class BookingViewSet(viewsets.ModelViewSet):
    """
    Core API for requesting services.
    Handles lifecycles of bookings and assignments.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', '') == 'CLIENT':
            return Booking.objects.filter(client__user=user)
        elif getattr(user, 'role', '') == 'WORKER':
            return Booking.objects.filter(assignments__worker__user=user)
        return Booking.objects.all()  # Admin sees all

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status not in ['PENDING', 'ASSIGNED']:
            return Response({"error": "Cannot cancel a booking in progress."}, status=status.HTTP_400_BAD_REQUEST)
        
        booking.status = 'CANCELLED'
        booking.save()
        return Response({"status": "booking cancelled"})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def assign_worker(self, request, pk=None):
        booking = self.get_object()
        worker_id = request.data.get('worker_id')
        worker = get_object_or_404(WorkerProfile, id=worker_id)
        
        assignment = Assignment.objects.create(
            booking=booking,
            worker=worker,
            status='PENDING_ACCEPTANCE'
        )
        
        booking.status = 'ASSIGNED'
        booking.save()
        
        return Response(AssignmentSerializer(assignment).data)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling mutual reviews between clients and workers.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically set the reviewer as the logged-in user
        serializer.save(reviewer=self.request.user)

    def get_queryset(self):
        user = self.request.user
        return Review.objects.filter(models.Q(reviewer=user) | models.Q(reviewee=user))
