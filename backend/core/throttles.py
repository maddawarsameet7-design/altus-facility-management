"""
core/throttles.py — Production-grade multi-layer authentication throttles.

Throttling architecture:
1. LoginUserIPThrottle (scope 'login_user_ip', default 5/min in prod):
   Strict limit keyed on (lowercased username + client IP).
   Prevents brute-force password guessing from a single IP.

2. LoginIPThrottle (scope 'login_ip', default 30/min in prod):
   Looser per-IP limit across all usernames.
   Protects endpoint from flooding multiple usernames from a single source.

3. LoginUsernameThrottle (scope 'login_user', default 20/hour in prod):
   Looser per-username limit across all IPs.
   Prevents distributed credential stuffing without locking out real users
   on another IP if an attacker fails a few attempts.

4. TokenRefreshThrottle (scope 'token_refresh', default 60/min in prod):
   Independent loose throttle for token refreshes so active users are never
   blocked by login brute-force throttles.

5. RegisterThrottle (scope 'register_ip', default 10/min in prod):
   Strict per-IP throttle for account creation.
"""
from rest_framework.throttling import SimpleRateThrottle


class DynamicRateThrottle(SimpleRateThrottle):
    """
    Base throttle that dynamically resolves rate & NUM_PROXIES from Django settings
    to allow dynamic testing and environment-based configuration.
    """
    def get_rate(self):
        from django.conf import settings
        from rest_framework.settings import api_settings
        drf_rates = getattr(settings, 'REST_FRAMEWORK', {}).get('DEFAULT_THROTTLE_RATES', {})
        if self.scope in drf_rates:
            return drf_rates[self.scope]
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope, '5/min')

    def get_ident(self, request):
        from django.conf import settings
        from rest_framework.settings import api_settings

        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        remote_addr = request.META.get('REMOTE_ADDR')

        num_proxies = getattr(settings, 'REST_FRAMEWORK', {}).get(
            'NUM_PROXIES', getattr(settings, 'NUM_PROXIES', api_settings.NUM_PROXIES)
        )

        if num_proxies is not None:
            if num_proxies == 0 or not xff:
                return remote_addr
            addrs = [a.strip() for a in xff.split(',') if a.strip()]
            if not addrs:
                return remote_addr
            client_addr = addrs[-min(num_proxies, len(addrs))]
            return client_addr.strip()

        return ''.join(xff.split()) if xff else remote_addr


class LoginUserIPThrottle(DynamicRateThrottle):
    """
    Strict limit keyed on (lowercased username + client IP), e.g. 5/min.
    An attacker on IP A guessing passwords cannot lock out the real user on IP B.
    """
    scope = 'login_user_ip'

    def get_cache_key(self, request, view):
        username = request.data.get('username')
        if not username:
            return None
        ident = self.get_ident(request)
        clean_user = str(username).lower().strip()
        return self.cache_format % {
            'scope': self.scope,
            'ident': f"{ident}_{clean_user}"
        }


class LoginIPThrottle(DynamicRateThrottle):
    """
    Looser per-IP limit across all usernames, e.g. 30/min.
    Prevents single-source endpoint flooding across random usernames.
    """
    scope = 'login_ip'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class LoginUsernameThrottle(DynamicRateThrottle):
    """
    Looser per-username limit across all IPs, e.g. 20/hour.
    Guards against distributed botnets targeting a single high-profile username,
    without enabling denial-of-service on legitimate users from other IPs.
    """
    scope = 'login_user'

    def get_cache_key(self, request, view):
        username = request.data.get('username')
        if not username:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': str(username).lower().strip()
        }


class TokenRefreshThrottle(DynamicRateThrottle):
    """
    Independent loose throttle for token refreshes (e.g. 60/min).
    Ensures active sessions are not blocked by login brute-force throttles.
    """
    scope = 'token_refresh'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class RegisterThrottle(DynamicRateThrottle):
    """
    Strict per-IP throttle for public account registration (e.g. 10/min).
    """
    scope = 'register_ip'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
