from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.throttling import ScopedRateThrottle
from core.throttles import (
    LoginUserIPThrottle, LoginIPThrottle, LoginUsernameThrottle, TokenRefreshThrottle
)


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle, LoginUserIPThrottle, LoginIPThrottle, LoginUsernameThrottle]
    throttle_scope = 'login'


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_classes = [TokenRefreshThrottle]
    throttle_scope = 'token_refresh'
from core.views import (
    ClientProfileViewSet, WorkerViewSet, PropertyViewSet, 
    ServiceCategoryViewSet, ServiceRequestViewSet,
    ReviewViewSet, ChatMessageViewSet, 
    UserProfileView, RegisterView, DashboardStatsView, DeviceTokenView,
    HealthCheckView
)
from core.views_attendance import (
    ClockInView, ClockOutView, MyAttendanceHistoryView,
    WorkerLocationUpdateView, AttendanceViewSet
)
from core.views_society import (
    SocietyViewSet, SiteViewSet, SocietySettingsViewSet, JoinSocietyView
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
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'societies', SocietyViewSet, basename='society')
router.register(r'sites', SiteViewSet, basename='site')
router.register(r'society-settings', SocietySettingsViewSet, basename='society-settings')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth endpoints (must be before the router include)
    path('api/auth/login/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/health/', HealthCheckView.as_view(), name='health_check'),
    
    # User profile & dashboard (must be before the router include)
    path('api/user/me/', UserProfileView.as_view(), name='user_profile'),
    path('api/user/device-token/', DeviceTokenView.as_view(), name='device_token'),
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # Payments
    path('api/payments/create-order/', CreateRazorpayOrderView.as_view(), name='create_payment_order'),
    path('api/payments/verify/', VerifyRazorpayPaymentView.as_view(), name='verify_payment'),
    
    # Attendance endpoints
    path('api/attendance/clock-in/', ClockInView.as_view(), name='clock_in'),
    path('api/attendance/clock-out/', ClockOutView.as_view(), name='clock_out'),
    path('api/attendance/my-history/', MyAttendanceHistoryView.as_view(), name='my_attendance_history'),
    
    # Worker location update (REST fallback)
    path('api/workers/location/', WorkerLocationUpdateView.as_view(), name='worker_location_update'),

    # Society join (invite code)
    path('api/societies/join/', JoinSocietyView.as_view(), name='society_join'),
    
    # Router-generated API endpoints
    path('api/', include(router.urls)),
]
