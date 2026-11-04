from datetime import datetime, timezone as dt_tz
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class WorkerAwareJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication extending SimpleJWT.
    Enforces Amendment 14:
    1. Checks token issue time (iat) against worker.sessions_revoked_at.
    2. Rejects inactive, suspended or exited workers on every request.
    """
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        if not user.is_active:
            raise exceptions.AuthenticationFailed("User account is inactive.", code='user_inactive')

        # Check worker status and session revocation
        if hasattr(user, 'worker_profile'):
            worker = user.worker_profile
            status = getattr(worker, 'verification_status', '') or ''
            if status in ['SUSPENDED', 'EXITED']:
                raise exceptions.AuthenticationFailed(
                    "Worker account is suspended or exited.",
                    code='worker_suspended'
                )

            revoked_at = getattr(worker, 'sessions_revoked_at', None)
            if revoked_at:
                iat = validated_token.get('iat')
                if iat:
                    token_issued_at = datetime.fromtimestamp(iat, tz=dt_tz.utc)
                    if token_issued_at < revoked_at:
                        raise exceptions.AuthenticationFailed(
                            "Worker session has been revoked. Please log in again.",
                            code='session_revoked'
                        )

        return user
