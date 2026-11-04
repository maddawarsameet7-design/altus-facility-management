from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, WorkerProfile, OTPChallenge, AuditLog, Society
from .permissions import IsDirectorOnly, IsOpsUser
from .otp_utils import normalize_phone, generate_otp_code, hash_otp_code, verify_otp_code
from .sms import send_otp_async


class WorkerOTPRequestView(APIView):
    """
    POST /api/auth/otp/request/
    Dispatches OTP verification code for worker phone login.
    Enforces:
    - Amendment 11: Anti-enumeration (identical response for staff, unknown, or valid worker phones).
    - 30-second resend cooldown per phone number.
    - Daily rate limits per phone and per IP.
    - Asynchronous SMS dispatch only to registered active workers.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_request'

    def post(self, request):
        phone_raw = request.data.get('phone', '').strip()
        if not phone_raw:
            return Response({"error": "phone is required."}, status=status.HTTP_400_BAD_REQUEST)

        phone = normalize_phone(phone_raw)
        if len(phone) < 8:
            return Response({"error": "Invalid phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        generic_response = {
            "message": "If the phone number is registered with an active worker account, a verification code has been sent.",
            "cooldown_seconds": 30
        }

        # ── 1. Cooldown Check (30 seconds) ──
        recent_challenge = OTPChallenge.objects.filter(
            phone=phone,
            created_at__gte=now - timedelta(seconds=30)
        ).first()
        if recent_challenge:
            remaining = max(1, 30 - int((now - recent_challenge.created_at).total_seconds()))
            return Response(
                {"error": f"Please wait {remaining} seconds before requesting a new code.", "cooldown_seconds": remaining},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # ── 2. Daily Caps (Per Phone & Per IP) ──
        phone_daily_count = OTPChallenge.objects.filter(
            phone=phone,
            created_at__gte=now - timedelta(hours=24)
        ).count()
        if phone_daily_count >= 10:
            return Response(
                {"error": "Daily verification limit reached for this phone number. Try again tomorrow."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()

        if ip:
            ip_daily_count = OTPChallenge.objects.filter(
                ip_address=ip,
                created_at__gte=now - timedelta(hours=24)
            ).count()
            if ip_daily_count >= 50:
                return Response(
                    {"error": "Too many requests from this network. Try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

        # ── 3. Worker Eligibility & Anti-Enumeration (Amendment 11) ──
        # Find active user with role='WORKER'
        user = User.objects.filter(
            role='WORKER',
            is_active=True
        ).filter(
            Q(worker_profile__phone=phone) |
            Q(worker_profile__phone=phone_raw) |
            Q(username=phone) |
            Q(username=phone_raw)
        ).select_related('worker_profile').first()

        # If user not found, or not a worker, or suspended/exited:
        # Return identical generic response and NEVER send SMS
        if not user or not hasattr(user, 'worker_profile'):
            return Response(generic_response, status=status.HTTP_200_OK)

        worker = user.worker_profile
        if getattr(worker, 'verification_status', '') in ['SUSPENDED', 'EXITED']:
            return Response(generic_response, status=status.HTTP_200_OK)

        # ── 4. Generate Challenge & Send Async SMS ──
        code = generate_otp_code(6)
        code_hash = hash_otp_code(phone, code)
        device_id = request.data.get('device_id', '').strip()
        expires_at = now + timedelta(minutes=5)

        OTPChallenge.objects.create(
            phone=phone,
            code_hash=code_hash,
            ip_address=ip,
            device_id=device_id,
            expires_at=expires_at
        )

        send_otp_async(phone, code)

        return Response(generic_response, status=status.HTTP_200_OK)


class WorkerOTPVerifyView(APIView):
    """
    POST /api/auth/otp/verify/
    Verifies OTP code and authenticates the worker, returning JWT access and refresh tokens.
    Enforces:
    - Amendment 11: Identical error response for invalid phone, incorrect code, or expired code.
    - Amendment 12: HMAC-SHA256 comparison via hmac.compare_digest.
    - Amendment 13: Only the newest challenge is valid; single atomic consumption.
    - Lockout after 5 failed attempts on a challenge.
    - Amendment 15: Device ID change tracking for supervisor review.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_verify'

    def post(self, request):
        phone_raw = request.data.get('phone', '').strip()
        code = request.data.get('code', '').strip()
        device_id = request.data.get('device_id', '').strip()

        generic_error = {"error": "Invalid or expired verification code."}

        if not phone_raw or not code:
            return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        phone = normalize_phone(phone_raw)
        now = timezone.now()

        # Amendment 13: Only the newest challenge is valid
        challenge = OTPChallenge.objects.filter(
            phone=phone,
            consumed_at__isnull=True
        ).order_by('-created_at').first()

        if not challenge:
            return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        # Lockout after 5 failed attempts
        if challenge.attempts >= 5:
            return Response(
                {"error": "Too many failed attempts. This code is locked. Please request a new verification code."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Expiry check
        if challenge.expires_at <= now:
            return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        # Code verification (Amendment 12: timing-safe hmac.compare_digest)
        if not verify_otp_code(phone, code, challenge.code_hash):
            challenge.attempts += 1
            challenge.save(update_fields=['attempts'])
            return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        # Atomic consumption (Amendment 13: rows == 0 prevents reuse)
        with transaction.atomic():
            rows = OTPChallenge.objects.filter(
                id=challenge.id,
                consumed_at__isnull=True
            ).update(consumed_at=now)

            if rows == 0:
                return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        # Find worker
        user = User.objects.filter(
            role='WORKER',
            is_active=True
        ).filter(
            Q(worker_profile__phone=phone) |
            Q(worker_profile__phone=phone_raw) |
            Q(username=phone) |
            Q(username=phone_raw)
        ).select_related('worker_profile').first()

        if not user or not hasattr(user, 'worker_profile'):
            return Response(generic_error, status=status.HTTP_400_BAD_REQUEST)

        worker = user.worker_profile
        if getattr(worker, 'verification_status', '') in ['SUSPENDED', 'EXITED']:
            return Response(
                {"error": "Worker account is suspended or exited. Contact operations."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Amendment 15: Device ID change tracking
        new_device_detected = False
        if device_id:
            if worker.device_id and worker.device_id != device_id:
                new_device_detected = True
                worker.new_device_approved = False
                worker.device_id = device_id
            elif not worker.device_id:
                worker.device_id = device_id

        worker.last_login_at = now
        worker.save(update_fields=['device_id', 'new_device_approved', 'last_login_at'])

        # Issue JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "worker_id": str(worker.id),
            "username": user.username,
            "verification_status": worker.verification_status,
            "new_device_detected": new_device_detected,
            "new_device_approved": worker.new_device_approved
        }, status=status.HTTP_200_OK)


class RevokeWorkerSessionsView(APIView):
    """
    POST /api/workers/{id}/revoke-sessions/
    Director-only action to immediately invalidate all existing JWT sessions for a worker.
    Amendment 14: Updates sessions_revoked_at. All subsequent requests with token iat < sessions_revoked_at
    will be rejected by WorkerAwareJWTAuthentication.
    """
    permission_classes = [permissions.IsAuthenticated, IsDirectorOnly]

    def post(self, request, pk):
        worker = get_object_or_404(WorkerProfile.objects.select_related('user'), id=pk)
        now = timezone.now()
        reason = request.data.get('reason', 'Sessions revoked by director.').strip()

        worker.sessions_revoked_at = now
        worker.save(update_fields=['sessions_revoked_at'])

        # Audit action
        target_society = None
        asgn = worker.roster_assignments.first()
        if asgn:
            target_society = asgn.society
        else:
            target_society = Society.objects.first()

        if target_society:
            AuditLog.objects.create(
                society=target_society,
                actor=request.user,
                action='REVOKE_WORKER_SESSIONS',
                target_model='WorkerProfile',
                target_id=worker.id,
                changes={'sessions_revoked_at': now.isoformat()},
                reason=reason
            )

        return Response({
            "status": "Worker sessions revoked successfully.",
            "worker_id": str(worker.id),
            "sessions_revoked_at": now.isoformat()
        }, status=status.HTTP_200_OK)


class IssueFallbackLoginCodeView(APIView):
    """
    POST /api/workers/{id}/issue-login-code/
    Supervisor/Director can issue a one-time login code for a worker.
    - Expires in 10 minutes.
    - Single use (via OTPChallenge table with device_id='FALLBACK_LOGIN').
    - Fully audited in AuditLog.
    - Never logged or stored in plain text.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def post(self, request, pk):
        worker = get_object_or_404(WorkerProfile.objects.select_related('user'), id=pk)
        if getattr(worker, 'verification_status', '') in ['SUSPENDED', 'EXITED']:
            return Response(
                {"error": "Cannot issue fallback login code for suspended or exited worker."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not worker.phone:
            return Response(
                {"error": "Worker has no registered phone number."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '').strip()
        if not reason:
            reason = f"Fallback login code issued by {request.user.role} ({request.user.username})"

        now = timezone.now()
        expires_at = now + timedelta(minutes=10)
        code = generate_otp_code(6)
        code_hash = hash_otp_code(worker.phone, code)

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()

        # Invalidate previous unconsumed fallback codes for this phone
        OTPChallenge.objects.filter(
            phone=worker.phone,
            device_id='FALLBACK_LOGIN',
            consumed_at__isnull=True
        ).update(consumed_at=now)

        # Store HMAC hashed challenge — code is NEVER stored in plain text
        OTPChallenge.objects.create(
            phone=worker.phone,
            code_hash=code_hash,
            ip_address=ip,
            device_id='FALLBACK_LOGIN',
            expires_at=expires_at
        )

        # Target society for AuditLog
        target_society = None
        asgn = worker.roster_assignments.first()
        if asgn:
            target_society = asgn.society
        else:
            target_society = Society.objects.first()

        if target_society:
            AuditLog.objects.create(
                society=target_society,
                actor=request.user,
                action='ISSUE_FALLBACK_LOGIN_CODE',
                target_model='WorkerProfile',
                target_id=worker.id,
                changes={
                    'expires_at': expires_at.isoformat(),
                    'phone': worker.phone,
                    'issued_by': request.user.username
                },
                reason=reason
            )

        # Returned once to the authorized supervisor in the HTTPS response payload.
        # NEVER recorded in logger or stored in database.
        return Response({
            "status": "Fallback login code issued successfully.",
            "worker_id": str(worker.id),
            "phone": worker.phone,
            "login_code": code,
            "expires_at": expires_at.isoformat(),
            "expires_in_minutes": 10
        }, status=status.HTTP_200_OK)


class ApproveWorkerDeviceView(APIView):
    """
    POST /api/workers/{id}/device-approval/
    Supervisor/Director approves or rejects a worker's new device.
    Until approved, financial data (bank details and payslips) remains redacted.
    """
    permission_classes = [permissions.IsAuthenticated, IsOpsUser]

    def post(self, request, pk):
        worker = get_object_or_404(WorkerProfile.objects.select_related('user'), id=pk)
        approved = bool(request.data.get('approved', False))
        reason = request.data.get('reason', '').strip()
        if not reason:
            reason = f"Device {'approved' if approved else 'rejected'} by {request.user.role} ({request.user.username})"

        worker.new_device_approved = approved
        worker.save(update_fields=['new_device_approved'])

        target_society = None
        asgn = worker.roster_assignments.first()
        if asgn:
            target_society = asgn.society
        else:
            target_society = Society.objects.first()

        if target_society:
            AuditLog.objects.create(
                society=target_society,
                actor=request.user,
                action='APPROVE_DEVICE' if approved else 'REJECT_DEVICE',
                target_model='WorkerProfile',
                target_id=worker.id,
                changes={'new_device_approved': approved, 'device_id': worker.device_id},
                reason=reason
            )

        return Response({
            "status": f"Device {'approved' if approved else 'rejected'} successfully.",
            "worker_id": str(worker.id),
            "new_device_approved": worker.new_device_approved
        }, status=status.HTTP_200_OK)


class WorkerPayslipView(APIView):
    """
    GET /api/workers/{id}/payslips/
    Endpoint returning worker compensation and payslip records.
    Item 6: Until a Supervisor approves a new device, access to payslips and bank data is locked.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        worker = get_object_or_404(WorkerProfile.objects.select_related('user'), id=pk)

        # Worker can view their own; Ops users can view any
        is_owner = (request.user.id == worker.user_id)
        is_ops = (getattr(request.user, 'role', '') in ('SUPERVISOR', 'DIRECTOR'))
        if not (is_owner or is_ops):
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        # Lock access if new device is not approved
        if not getattr(worker, 'new_device_approved', True):
            return Response(
                {"error": "Access to payslips and financial details is restricted until your new device is approved by a supervisor."},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            "worker_id": str(worker.id),
            "bank_account_number": worker.bank_account_number,
            "bank_ifsc": worker.bank_ifsc,
            "compensation_rate": str(worker.compensation_rate),
            "payslips": []
        }, status=status.HTTP_200_OK)


