from rest_framework import permissions

class IsClientUser(permissions.BasePermission):
    """
    Allows access only to users with the 'CLIENT' role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', '') == 'CLIENT')

class IsWorkerUser(permissions.BasePermission):
    """
    Allows access only to users with the 'WORKER' role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', '') == 'WORKER')

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to platform administrators.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', '') == 'ADMIN')

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object (like a booking or property) 
    or admins to edit/view it.
    """
    def has_object_permission(self, request, view, obj):
        # Admin always has permission
        if getattr(request.user, 'role', '') == 'ADMIN':
            return True
            
        # Check ownership based on object type
        # For Booking
        if hasattr(obj, 'client'):
            return obj.client.user == request.user
            
        # For Property
        if hasattr(obj, 'client'): 
            return obj.client.user == request.user
            
        # For Assignment (Worker check)
        if hasattr(obj, 'worker'):
            return obj.worker.user == request.user
            
        return False
