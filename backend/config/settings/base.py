"""Base Django settings shared by all environments.

Configuration is environment-driven (see ``.env.example``). Environment-specific
overrides live in ``dev.py`` and ``prod.py``. Select with::

    DJANGO_SETTINGS_MODULE=config.settings.dev   # local
    DJANGO_SETTINGS_MODULE=config.settings.prod  # production

Contract references: env vars (§3.8), Celery queues/tasks (§3.9), settings
keys (§3.10), response envelope & pagination (§3.7).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dj_database_url

from core import constants

# Optionally load a local .env file if python-dotenv is installed.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional in prod
    pass


# ── env helpers ───────────────────────────────────────────────────────────────
def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return str(os.environ.get(key, default)).lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# backend/  (config/settings/base.py -> config/settings -> config -> backend)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY") or env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,api.stampn.net")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "https://stampn.net,https://app.stampn.net,https://api.stampn.net",
)

# Public HTTPS origin — used to build Apple webServiceURL and Google save URLs.
BASE_URL = env("BASE_URL", "http://localhost:8000")

# Where the public customer enrollment page lives (the dashboard app). The QR
# join_url points here so scanning opens the branded join form, not the API.
ENROLL_BASE_URL = env("ENROLL_BASE_URL", "https://app.stampn.net")

# The merchant dashboard app — support emails (password reset / invite links,
# Phase 6) point here.
DASHBOARD_BASE_URL = env("DASHBOARD_BASE_URL", "https://app.stampn.net")

# ── Email (SMTP) ──────────────────────────────────────────────────────────────
# Outbound mail: password-reset / invite links and admin replies to contact
# messages. All values are env-driven (see .env.example). The default backend is
# the console backend, which prints emails to stdout and never sends or fails —
# safe for local dev and CI. Production overrides EMAIL_BACKEND to real SMTP in
# prod.py; set EMAIL_HOST_PASSWORD as a secret on the server (never commit it).
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.hostinger.com")
EMAIL_PORT = int(env("EMAIL_PORT", "465") or "465")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "contact@stampn.net")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Stampn Support <contact@stampn.net>")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "20") or "20")

# ── Applications ──────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",  # queryable TaskResult table for the ops task monitor (Phase 14)
    # Tracks issued refresh tokens (OutstandingToken) so a password change can
    # blacklist every existing session. Ships its own migrations.
    "rest_framework_simplejwt.token_blacklist",
]

# All persistent models live in ``core`` (contract §3.4). The other apps own
# behaviour (views/services/tasks) but no models, so a single core migration is
# the only schema source of truth in Phase 1.0.
LOCAL_APPS = [
    "core",
    "accounts",
    "enrollment",
    "wallets",
    "loyalty",
    "dashboard",
    "billing",
    "messaging",
    "branding",  # registration-page theme + QR styling (finalize Phase 1)
    "console",  # platform admin panel (separate auth boundary)
    "partners",  # merchant-referral program (Phase E.1)
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "common.middleware.RequestIDMiddleware",  # first: correlation id for all logs
    "corsheaders.middleware.CorsMiddleware",  # before CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static behind Caddy
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.StaffContextMiddleware",  # attaches request.staff
    "common.middleware.MaintenanceModeMiddleware",  # 503s merchant API in maintenance (Phase 14)
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
# Production: DATABASE_URL=postgres://...  (contract §3.8).
# Local dev: unset -> SQLite, so the exit-criteria shell runs without Postgres.
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalization ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Africa/Cairo")
USE_I18N = True
USE_TZ = True

# ── Static / media files ──────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Uploads (Phase 1.6) ───────────────────────────────────────────────────────
UPLOAD_MAX_SIZE_BYTES = int(
    (env("UPLOAD_MAX_SIZE_BYTES", "5_000_000") or "5_000_000").replace("_", "")
)
# SVG is intentionally excluded — it can embed <script> (stored-XSS risk when
# served inline). Add it back only behind attachment/CSP serving.
UPLOAD_ALLOWED_TYPES = frozenset(
    env_list("UPLOAD_ALLOWED_TYPES", "image/jpeg,image/png,image/webp")
)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    # localhost 5173 marketing · 5174 dashboard · 5175 admin console dev;
    # prod: marketing + dashboard + admin console.
    "http://localhost:5173,http://localhost:5174,http://localhost:5175,"
    "https://stampn.net,https://app.stampn.net,https://admin.stampn.net",
)

# Allow the dashboard (different origin) to send the loyalty Idempotency-Key on
# cross-origin stamp/redeem requests — preflight would otherwise reject it.
from corsheaders.defaults import default_headers as _cors_default_headers  # noqa: E402

CORS_ALLOW_HEADERS = (*_cors_default_headers, "idempotency-key")

# ── Django REST Framework (contract §3.7, §3.10) ──────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # SimpleJWT + the Phase 6 impersonation guard (identical for normal tokens).
        "common.auth.MerchantJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultCursorPagination",
    "PAGE_SIZE": constants.DEFAULT_PAGE_SIZE,
    "EXCEPTION_HANDLER": "common.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Edge rate-limiting (Phase 1.8). ScopedRateThrottle no-ops on any view that
    # doesn't set ``throttle_scope``, so this only bites the sensitive endpoints
    # that opt in (auth brute-force surface + the unauthenticated webhooks).
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": env("THROTTLE_AUTH", "20/min"),
        "webhook": env("THROTTLE_WEBHOOK", "120/min"),
        "admin_auth": env("THROTTLE_ADMIN_AUTH", "10/min"),
        # Public "Get started" lead intake from the marketing site.
        "lead_intake": env("THROTTLE_LEAD_INTAKE", "10/min"),
        # Logged-in merchant opening a support message from the dashboard.
        "support_message": env("THROTTLE_SUPPORT_MESSAGE", "10/min"),
    },
}

# Throttle counters live in the cache; use Redis in prod so they're shared across
# web workers (LocMem is per-process — fine for local/tests).
_redis_url = env("REDIS_URL", "")
CACHES = {
    "default": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
        }
        if _redis_url
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    )
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": __import__("datetime").timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": __import__("datetime").timedelta(days=14),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Stampn API",
    "DESCRIPTION": (
        "Digital loyalty & wallet-pass platform. Merchant API under `/api/v1` and "
        "the admin console under `/api/admin/v1`. This document is generated from "
        "the live code by drf-spectacular — `contracts/openapi.yaml` is the "
        "committed snapshot and CI fails if it drifts from the served schema."
    ),
    "VERSION": "1.2.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": "core.enums.Role",
    },
}

# ── Custom wallet settings (contract §3.10) ───────────────────────────────────
WALLET = {
    "APPLE": {
        "PASS_TYPE_ID": env("APPLE_PASS_TYPE_ID", "pass.net.stampn.loyalty"),
        "TEAM_ID": env("APPLE_TEAM_ID", ""),
        "PASS_CERT_PATH": env("APPLE_PASS_CERT_PATH", ""),
        "PASS_CERT_PASSWORD": env("APPLE_PASS_CERT_PASSWORD", ""),
        "WWDR_CERT_PATH": env("APPLE_WWDR_CERT_PATH", ""),
        "APNS_USE_SANDBOX": env_bool("APNS_USE_SANDBOX", False),
    },
    "GOOGLE": {
        "ISSUER_ID": env("GOOGLE_WALLET_ISSUER_ID", ""),
        "SA_KEY_PATH": env("GOOGLE_SA_KEY_PATH", ""),
    },
}

# ── Billing gateways (Phase 1.7 · contract §3.10) ─────────────────────────────
# Paymob credentials. Unset locally/CI → the adapter runs in stub mode
# (deterministic checkout URL, no network); real creds are wired on staging.
#
# Recurring subscriptions need a second set of credentials beyond the legacy
# Accept API's: SECRET_KEY/PUBLIC_KEY drive the Intention API + Unified Checkout,
# and the two integration ids play different roles — CARD_INTEGRATION_ID runs the
# one-time 3DS card-linking charge, MOTO_INTEGRATION_ID is attached to the Paymob
# Subscription Plan and runs the unattended recurring deductions.
BILLING = {
    "PAYMOB": {
        "API_KEY": env("PAYMOB_API_KEY", ""),
        "HMAC_SECRET": env("PAYMOB_HMAC_SECRET", ""),
        "SECRET_KEY": env("PAYMOB_SECRET_KEY", ""),
        "PUBLIC_KEY": env("PAYMOB_PUBLIC_KEY", ""),
        "CARD_INTEGRATION_ID": env("PAYMOB_CARD_INTEGRATION_ID", "")
        # Back-compat: this was PAYMOB_INTEGRATION_ID before the card/Moto split.
        or env("PAYMOB_INTEGRATION_ID", ""),
        "MOTO_INTEGRATION_ID": env("PAYMOB_MOTO_INTEGRATION_ID", ""),
    },
}

# Google Wallet requires every LoyaltyClass to carry a program logo. When a
# merchant/card has no logo_url, fall back to this self-hosted default (served
# by WhiteNoise at <BASE_URL>/static/wallet/logo.png). Must be publicly
# reachable over HTTPS for Google to fetch it.
WALLET_DEFAULT_LOGO_URL = env("WALLET_DEFAULT_LOGO_URL", "") or f"{BASE_URL}/static/wallet/logo.png"

# Platform (Kasbana) watermark/logo rendered at the bottom-left of every wallet
# pass — the "Powered by" branding slot. Leave blank to render a drawn
# PLACEHOLDER badge (the slot is wired and ready; drop the real asset in here).
# Must be a local /uploads URL (read via _local_media_bytes — no SSRF).
WALLET_PLATFORM_LOGO_URL = env("WALLET_PLATFORM_LOGO_URL", "")

# Platform label shown as Apple ``logoText`` beside the top-left brand logo
# ("[BrandLogo] Stampn"). Apple store cards have no right-side image slot, so the
# platform attribution rides here as text. Blank → no platform label.
WALLET_PLATFORM_LABEL = env("WALLET_PLATFORM_LABEL", "Stampn")

# Mirror selected contract constants into settings for callers that read them
# from settings (contract §3.10).
STAMP_COOLDOWN_SECONDS = constants.STAMP_COOLDOWN_SECONDS

# ── Celery (contract §3.9) ────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL") or env("REDIS_URL", "redis://localhost:6379/0")
# Fail fast when the broker is unreachable so a best-effort enqueue (e.g. the
# live wallet-pass update on a till stamp) can never hang the web request or its
# open DB transaction until gunicorn times out (which surfaced as a browser
# "network error"). ``wallets.service._enqueue`` catches the resulting error.
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_timeout": 2, "socket_connect_timeout": 2}
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
# Don't retry a publish when the broker is down — fail fast so the caller's
# best-effort enqueue returns immediately instead of retrying for seconds.
CELERY_TASK_PUBLISH_RETRY = False
# Results land in Postgres (django_celery_results) so the Phase 14 ops task monitor
# can query/retry them; nothing reads results synchronously, so this is safe.
# RESULT_EXTENDED stores the task name + args, which the retry action re-enqueues.
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND") or "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_QUEUES: dict[str, dict] = {
    "default": {},
    "wallet": {},
    "messaging": {},
}
# Route canonical tasks to their queues (contract §3.9).
CELERY_TASK_ROUTES = {
    "wallets.tasks.*": {"queue": "wallet"},
    "messaging.tasks.*": {"queue": "messaging"},
    "core.tasks.*": {"queue": "default"},
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    # Lock merchants whose 14-day trial elapsed without converting (Phase 1.4).
    "billing-expire-trials": {
        "task": "billing.tasks.expire_trials",
        "schedule": 3600.0,  # hourly
    },
    # Lock subs whose period-end cancel has lapsed (note 6 — cancel keeps access
    # until the period ends). effective_plan already locks lazily; this tidies
    # the stored status so queries/dashboard reflect the cancellation.
    "billing-expire-scheduled-cancels": {
        "task": "billing.tasks.expire_scheduled_cancellations",
        "schedule": 3600.0,  # hourly
    },
    # Re-attempt suspends that never reached Paymob. A cancel is always recorded
    # locally, even if the gateway call fails — without this sweep such a
    # merchant keeps getting deducted while believing they cancelled.
    "billing-retry-pending-gateway-cancels": {
        "task": "billing.tasks.retry_pending_gateway_cancels",
        "schedule": 3600.0,  # hourly
    },
    # Fire date-driven engage automations (birthday/expiry/winback) (Phase 1.7).
    "messaging-scan-automations": {
        "task": "messaging.tasks.scan_automations",
        "schedule": 86400.0,  # daily
    },
    # Dispatch scheduled campaigns whose send time has arrived (roadmap Phase 2).
    "messaging-send-due-campaigns": {
        "task": "messaging.tasks.send_due_campaigns",
        "schedule": 60.0,  # every minute (near-real-time scheduled sends)
    },
    # Dispatch scheduled admin announcements whose send time has arrived (Phase 10).
    "console-send-due-announcements": {
        "task": "console.tasks.send_due_announcements",
        "schedule": 300.0,  # every 5 minutes
    },
}
CELERY_TASK_ACKS_LATE = True
CELERY_TIMEZONE = TIME_ZONE

# ── Structured logging (Phase D) ──────────────────────────────────────────────
# JSON logs (one object per line) with a request-id correlation field, so prod
# logs are queryable. Format is env-controlled: `console` (human-readable) is the
# default for local dev; prod sets LOG_FORMAT=json. Both attach RequestIDFilter.
LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOG_FORMAT = env("LOG_FORMAT", "console")  # "json" in prod

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "common.logging.RequestIDFilter"},
    },
    "formatters": {
        "json": {"()": "common.logging.JSONFormatter"},
        "console": {
            "format": "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "json" if LOG_FORMAT == "json" else "console",
        },
    },
    "root": {"handlers": ["default"], "level": LOG_LEVEL},
    "loggers": {
        # Django's request logger duplicates 4xx/5xx we already surface; keep it
        # at ERROR so the JSON stream isn't noisy with WARNING 404s.
        "django.request": {"level": "ERROR", "handlers": ["default"], "propagate": False},
    },
}

# ── Observability — Sentry (Phase 5) ──────────────────────────────────────────
# No-op unless SENTRY_DSN is set, so dev/CI stay silent. In prod the DSN comes
# from infra/.env; SENTRY_RELEASE is the deployed image tag (compose passes
# IMAGE_TAG) so every issue is tied to the exact deploy it came from.
SENTRY_DSN = env("SENTRY_DSN", "")
if SENTRY_DSN and "pytest" not in sys.modules:  # never report from the test suite
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    # Profiling defaults to OFF (0.0) to protect the free-tier quota; bump
    # SENTRY_PROFILE_SESSION_SAMPLE_RATE when you want CPU profiles.
    _profile_rate = float(env("SENTRY_PROFILE_SESSION_SAMPLE_RATE", "0.0") or 0.0)
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env("SENTRY_ENVIRONMENT", "production"),
        release=env("SENTRY_RELEASE") or None,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", "0.1") or 0.1),
        send_default_pii=env_bool("SENTRY_SEND_PII", False),
        # Forward Python logging (logger.error/warning/…) to Sentry.
        enable_logs=env_bool("SENTRY_ENABLE_LOGS", True),
        profile_session_sample_rate=_profile_rate,
        profile_lifecycle="trace",
    )
