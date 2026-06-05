from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from core.views import (
    ClientProfileViewSet, WorkerViewSet, PropertyViewSet, 
    ServiceCategoryViewSet, ServiceRequestViewSet,
    ReviewViewSet, ChatMessageViewSet, 
    UserProfileView, RegisterView, DashboardStatsView, DeviceTokenView
)
from core.views_payments import CreateRazorpayOrderView, VerifyRazorpayPaymentView

router = DefaultRouter()
router.register(r'clients', ClientProfileViewSet, basename='client')
router.register(r'workers', WorkerViewSet, basename='worker')
router.register(r'properties', PropertyViewSet, basename='property')
router.register(r'services', ServiceCategoryViewSet, basename='service')
router.register(r'requests', ServiceRequestViewSet, basename='request')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'chats', ChatMessageViewSet, basename='chat')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth endpoints (must be before the router include)
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    
    # User profile & dashboard (must be before the router include)
    path('api/user/me/', UserProfileView.as_view(), name='user_profile'),
    path('api/user/device-token/', DeviceTokenView.as_view(), name='device_token'),
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # Payments
    path('api/payments/create-order/', CreateRazorpayOrderView.as_view(), name='create_payment_order'),
    path('api/payments/verify/', VerifyRazorpayPaymentView.as_view(), name='verify_payment'),
    
    # Router-generated API endpoints
    path('api/', include(router.urls)),
]
