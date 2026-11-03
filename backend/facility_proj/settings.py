import os
from datetime import timedelta
from pathlib import Path
import dj_database_url

try:
    from dotenv import load_dotenv
    _backend_env = Path(__file__).resolve().parent.parent / '.env'
    _root_env = Path(__file__).resolve().parent.parent.parent / '.env'
    if _backend_env.exists():
        load_dotenv(_backend_env)
    elif _root_env.exists():
        load_dotenv(_root_env)
    else:
        load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-production-ready-key-change-this')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')

# Razorpay Keys
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_YourTestKeyIdHere')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'YourTestKeySecretHere')

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
elif DEBUG:
    ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1']
else:
    ALLOWED_HOSTS = ['altsan.com', 'api.altsan.com']

RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    'https://altsan.com',
    'https://www.altsan.com',
    'https://api.altsan.com',
    'https://*.ngrok-free.app'
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

INSTALLED_APPS = [
    'daphne',
    'channels',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'storages',
    
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.CurrentUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'facility_proj.urls'
ASGI_APPLICATION = 'facility_proj.asgi.application'
WSGI_APPLICATION = 'facility_proj.wsgi.application'

if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [os.environ.get('REDIS_URL')],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'altus',        # must match pgAdmin
        'USER': 'postgres',
        'PASSWORD': '1234',     # must match what you set
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

database_url = os.environ.get('DATABASE_URL')
if database_url:
    try:
        import socket
        from urllib.parse import urlparse
        parsed_url = urlparse(database_url)
        hostname = parsed_url.hostname
        if hostname and hostname not in ('localhost', '127.0.0.1'):
            socket.getaddrinfo(hostname, None)
        DATABASES['default'] = dj_database_url.config(conn_max_age=600, conn_health_checks=True)
    except Exception as e:
        import logging
        logging.warning(f"DATABASE_URL host failed DNS resolution ({e}). Gracefully falling back to SQLite.")
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }

AUTH_USER_MODEL = 'core.User'

# ── Reverse Proxy IP Configuration ───────────────────────────
NUM_PROXIES = int(os.environ.get('NUM_PROXIES', 1 if not DEBUG else 0))

# ── Throttling Configuration ──────────────────────────────────
LOGIN_USER_IP_THROTTLE_RATE = os.environ.get('LOGIN_USER_IP_THROTTLE_RATE', '60/min' if DEBUG else '5/min')
LOGIN_IP_THROTTLE_RATE = os.environ.get('LOGIN_IP_THROTTLE_RATE', '120/min' if DEBUG else '30/min')
LOGIN_USER_THROTTLE_RATE = os.environ.get('LOGIN_USER_THROTTLE_RATE', '120/hour' if DEBUG else '20/hour')
TOKEN_REFRESH_THROTTLE_RATE = os.environ.get('TOKEN_REFRESH_THROTTLE_RATE', '120/min' if DEBUG else '60/min')
REGISTER_THROTTLE_RATE = os.environ.get('REGISTER_THROTTLE_RATE', '60/min' if DEBUG else '10/min')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'NUM_PROXIES': NUM_PROXIES,
    # ── RBAC: deny by default, each view overrides as needed ──
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # ── Throttling: protect against brute-force & abuse ───────
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/min' if DEBUG else '20/min',
        'user': '1000/min' if DEBUG else '200/min',
        'login': LOGIN_USER_IP_THROTTLE_RATE,
        'login_user_ip': LOGIN_USER_IP_THROTTLE_RATE,
        'login_ip': LOGIN_IP_THROTTLE_RATE,
        'login_user': LOGIN_USER_THROTTLE_RATE,
        'token_refresh': TOKEN_REFRESH_THROTTLE_RATE,
        'register_ip': REGISTER_THROTTLE_RATE,
        'society_join': '60/hour' if DEBUG else '10/hour',
    },
    # ── Pagination ─────────────────────────────────────────────
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOW_ALL_ORIGINS = bool(DEBUG)
CORS_EXPOSE_HEADERS = ['Retry-After']

cors_env = os.environ.get('CORS_ALLOWED_ORIGINS')
if cors_env:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_env.split(',') if origin.strip()]
elif DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ]
else:
    CORS_ALLOWED_ORIGINS = []

if RENDER_EXTERNAL_HOSTNAME and f'https://{RENDER_EXTERNAL_HOSTNAME}' not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

TIME_ZONE = 'UTC'
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

if os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_STORAGE_BUCKET_NAME'):
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'ap-south-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_DEFAULT_ACL = 'public-read'
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Ensure staticfiles directory exists to eliminate startup warning
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

# ── Fast Password Hasher for Tests ──────────────────────────────────────────
import sys
if 'pytest' in sys.modules or any('test' in arg for arg in sys.argv):
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]

