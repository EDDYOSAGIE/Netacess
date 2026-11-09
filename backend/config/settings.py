import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=""):
    return os.environ.get(name, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

if not DEBUG:
    if len(SECRET_KEY) < 50 or SECRET_KEY == "dev-insecure-key-change-me":
        raise ImproperlyConfigured("Production requires a unique DJANGO_SECRET_KEY of at least 50 characters")
    if not ALLOWED_HOSTS or all(host in {"localhost", "127.0.0.1"} for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured("Production requires DJANGO_ALLOWED_HOSTS to contain the public hostname")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    if env("DJANGO_TRUST_X_FORWARDED_PROTO").lower() == "true":
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts",
    "apps.plans",
    "apps.orders",
    "apps.payments",
    "apps.access_codes",
    "apps.notifications",
    "apps.adminops",
    "apps.sms",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# --- Database: SQLite by default, any Postgres (Supabase) via DATABASE_URL ---
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60
    )
}
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    # Needed when connecting through Supabase's transaction pooler (PgBouncer)
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Cache / Celery ---
REDIS_URL = env("REDIS_URL")
USE_REDIS = env("USE_REDIS", "true" if REDIS_URL else "false").lower() == "true"
if USE_REDIS:
    if not REDIS_URL:
        raise ImproperlyConfigured("REDIS_URL is required when USE_REDIS=true")
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
    CELERY_BROKER_URL = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }}
    CELERY_BROKER_URL = "memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.TokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.NewestFirst",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"otp": "3/hour", "payments": "30/min"},
}

# --- Netacess settings ---
SMS_PROVIDER = env("SMS_PROVIDER", "console").lower()
TERMII_API_KEY = env("TERMII_API_KEY")
TERMII_BASE_URL = env("TERMII_BASE_URL", "https://api.ng.termii.com").rstrip("/")
TERMII_SENDER_ID = env("TERMII_SENDER_ID", "N-Alert")
TERMII_CHANNEL = env("TERMII_CHANNEL", "dnd")
SMS_ALLOWLIST = [n.strip() for n in env("SMS_ALLOWLIST").split(",") if n.strip()]
DEMO_MODE = env("DEMO_MODE", "false").lower() == "true"
if not DEBUG and SMS_PROVIDER == "console" and not DEMO_MODE:
    raise ImproperlyConfigured("Configure a real SMS_PROVIDER before running in production")
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 60
OTP_MAX_PER_HOUR = 3
AUTH_IDLE_TIMEOUT_SECONDS = 3600
ACCESS_CODE_ENC_KEY = env("ACCESS_CODE_ENC_KEY")
FLUTTERWAVE_SECRET_KEY = env("FLUTTERWAVE_SECRET_KEY")
FLUTTERWAVE_WEBHOOK_HASH = env("FLUTTERWAVE_WEBHOOK_HASH")
ESPEES_API_BASE = env("ESPEES_API_BASE")
ESPEES_API_TOKEN = env("ESPEES_API_TOKEN")
ESPEES_MERCHANT_WALLET = env("ESPEES_MERCHANT_WALLET")
# Keep customer Espees checkout disabled until confirmations can be matched to individual orders.
ESPEES_CHECKOUT_READY = env("ESPEES_CHECKOUT_READY", "0") == "1"
FRONTEND_URL = env("FRONTEND_URL", "http://127.0.0.1:3000")
PAYMENT_PENDING_EXPIRY_MINUTES = 60

# --- Staff alerts ---
ADMIN_ALERT_EMAILS = [e.strip() for e in env("ADMIN_ALERT_EMAILS").split(",") if e.strip()]  # extra recipients
ADMIN_ALERT_SMS = env("ADMIN_ALERT_SMS", "1") == "1"  # SMS to staff phones
ADMIN_REVIEW_REMINDER_MINUTES = 60
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Netacess <alerts@netacess.local>")
