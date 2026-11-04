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
from core.views_otp import (
    WorkerOTPRequestView, WorkerOTPVerifyView, RevokeWorkerSessionsView
)
from core.views_attendance import (
    ClockInView, ClockOutView, MyAttendanceHistoryView,
    WorkerLocationUpdateView, AttendanceViewSet
)
from core.views_society import (
    SocietyViewSet, SiteViewSet, SocietySettingsViewSet, JoinSocietyView
)
from core.views_payments import CreateRazorpayOrderView, VerifyRazorpayPaymentView
from core.views_staffing import (
    PostViewSet, ShiftViewSet, RosterAssignmentViewSet, DailyRosterViewSet,
    LeaveRecordViewSet, AlertViewSet, AuditLogViewSet,
    RosterClockInView, RosterClockOutView, RosterBoardTodayView,
    MyScheduleView, MarkSlotAbsentView, UnfilledRosterView,
    AttendanceCorrectionView, SelfieDownloadView,
    ReplacementRequestViewSet, MyOffersView, AcceptOfferView,
    DeclineOfferView, ReplacementMetricsView, NotificationViewSet
)

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
router.register(r'roster/posts', PostViewSet, basename='roster-post')
router.register(r'roster/shifts', ShiftViewSet, basename='roster-shift')
router.register(r'roster/assignments', RosterAssignmentViewSet, basename='roster-assignment')
router.register(r'roster/daily', DailyRosterViewSet, basename='roster-daily')
router.register(r'roster/leaves', LeaveRecordViewSet, basename='roster-leave')
router.register(r'roster/alerts', AlertViewSet, basename='roster-alert')
router.register(r'roster/audit-logs', AuditLogViewSet, basename='roster-audit-log')
router.register(r'roster/replacements', ReplacementRequestViewSet, basename='roster-replacement')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth endpoints (must be before the router include)
    path('api/auth/login/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/otp/request/', WorkerOTPRequestView.as_view(), name='worker_otp_request'),
    path('api/auth/otp/verify/', WorkerOTPVerifyView.as_view(), name='worker_otp_verify'),
    path('api/health/', HealthCheckView.as_view(), name='health_check'),
    
    # User profile & dashboard (must be before the router include)
    path('api/user/me/', UserProfileView.as_view(), name='user_profile'),
    path('api/user/device-token/', DeviceTokenView.as_view(), name='device_token'),
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # Payments
    path('api/payments/create-order/', CreateRazorpayOrderView.as_view(), name='create_payment_order'),
    path('api/payments/verify/', VerifyRazorpayPaymentView.as_view(), name='verify_payment'),
    
    # Existing request-based attendance endpoints (untouched)
    path('api/attendance/clock-in/', ClockInView.as_view(), name='clock_in'),
    path('api/attendance/clock-out/', ClockOutView.as_view(), name='clock_out'),
    path('api/attendance/my-history/', MyAttendanceHistoryView.as_view(), name='my_attendance_history'),
    
    # Roster-based staffing attendance & operational endpoints
    path('api/roster/clock-in/', RosterClockInView.as_view(), name='roster_clock_in'),
    path('api/roster/clock-out/', RosterClockOutView.as_view(), name='roster_clock_out'),
    path('api/roster/today/', RosterBoardTodayView.as_view(), name='roster_board_today'),
    path('api/roster/my-schedule/', MyScheduleView.as_view(), name='roster_my_schedule'),
    path('api/roster/unfilled/', UnfilledRosterView.as_view(), name='roster_unfilled'),
    path('api/roster/<uuid:pk>/mark-absent/', MarkSlotAbsentView.as_view(), name='roster_mark_absent'),
    path('api/roster/attendance/<uuid:pk>/correct/', AttendanceCorrectionView.as_view(), name='roster_attendance_correct'),
    path('api/roster/attendance/<uuid:pk>/selfie/', SelfieDownloadView.as_view(), name='roster_attendance_selfie'),

    # Replacement workflow endpoints
    path('api/roster/my-offers/', MyOffersView.as_view(), name='roster_my_offers'),
    path('api/roster/offers/<uuid:pk>/accept/', AcceptOfferView.as_view(), name='roster_offer_accept'),
    path('api/roster/offers/<uuid:pk>/decline/', DeclineOfferView.as_view(), name='roster_offer_decline'),
    path('api/roster/replacements/metrics/', ReplacementMetricsView.as_view(), name='roster_replacements_metrics'),

    # Worker location update (REST fallback)
    path('api/workers/location/', WorkerLocationUpdateView.as_view(), name='worker_location_update'),
    path('api/workers/<uuid:pk>/revoke-sessions/', RevokeWorkerSessionsView.as_view(), name='worker_revoke_sessions'),

    # Society join (invite code)
    path('api/societies/join/', JoinSocietyView.as_view(), name='society_join'),
    
    # Router-generated API endpoints
    path('api/', include(router.urls)),
]
