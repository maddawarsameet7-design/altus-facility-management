from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from core.views import (
    ClientProfileViewSet, WorkerViewSet, PropertyViewSet, 
    ServiceCategoryViewSet, BookingViewSet
)

router = DefaultRouter()
router.register(r'clients', ClientProfileViewSet, basename='client')
router.register(r'workers', WorkerViewSet, basename='worker')
router.register(r'properties', PropertyViewSet, basename='property')
router.register(r'services', ServiceCategoryViewSet, basename='service')
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    
    # Auth endpoints
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
