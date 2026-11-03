"""
core/throttles.py — Production-grade dual-layer authentication throttles.
Protects login against brute-force (per-IP) and credential stuffing (per-username).
"""
from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    """
    Throttles authentication attempts per client IP address.
    Protects against single-source brute-force attacks.
    """
    scope = 'login_ip'

    def get_rate(self):
        from django.conf import settings
        from rest_framework.settings import api_settings
        drf_rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})
        if self.scope in drf_rates:
            return drf_rates[self.scope]
        if hasattr(settings, 'LOGIN_THROTTLE_RATE'):
            return settings.LOGIN_THROTTLE_RATE
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope, '5/min')

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class LoginUsernameThrottle(SimpleRateThrottle):
    """
    Throttles authentication attempts per targeted username across all IPs.
    Protects against distributed credential stuffing / botnet attacks.
    """
    scope = 'login_user'

    def get_rate(self):
        from django.conf import settings
        from rest_framework.settings import api_settings
        drf_rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})
        if self.scope in drf_rates:
            return drf_rates[self.scope]
        if hasattr(settings, 'LOGIN_THROTTLE_RATE'):
            return settings.LOGIN_THROTTLE_RATE
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope, '5/min')

    def get_cache_key(self, request, view):
        username = request.data.get('username')
        if not username:
            # If no username supplied, allow view validation to handle missing field
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': str(username).lower().strip()
        }
