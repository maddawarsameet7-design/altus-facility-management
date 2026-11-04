"""
facility_proj/test_settings.py — Test environment settings for pytest.
Inherits from standard settings, enables fast test password hashers,
and configures relaxed test throttle rates to prevent false 429 errors during bulk test runs.
"""
import copy
from .settings import *

# Fast password hasher for test suite execution speed
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Relaxed throttle rates for automated test runs
REST_FRAMEWORK = copy.deepcopy(REST_FRAMEWORK)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['otp_request'] = '60/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['otp_verify'] = '60/min'
