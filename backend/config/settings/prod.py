"""Production settings.

Requires a real ``SECRET_KEY``, ``DATABASE_URL`` (Postgres), ``REDIS_URL`` and
the wallet/billing secrets from the contract §3.8. Served over HTTPS (the Apple
Wallet web service requires it).
"""

from __future__ import annotations

from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = False

# Structured JSON logs in production (base.py defaults to console for local dev),
# unless an operator explicitly overrides LOG_FORMAT.
if env("LOG_FORMAT", "json") == "json":
    LOGGING["handlers"]["default"]["formatter"] = "json"  # type: ignore[index]  # noqa: F405

# Real SMTP in production (Hostinger). Host/port/user default from base.py; the
# password MUST be provided via the EMAIL_HOST_PASSWORD env var / server secret.
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

SECURE_CONTENT_TYPE_NOSNIFF = True

# Security hardening behind the TLS-terminating proxy (Caddy).
# HTTPS_ENABLED is gated so a fresh box can be brought up on plain HTTP over its
# IP, then flipped on once a domain + Let's Encrypt cert exist (required for
# Apple Wallet). Set HTTPS_ENABLED=true in infra/.env once DNS + TLS are ready.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
HTTPS_ENABLED = env_bool("HTTPS_ENABLED", True)
SECURE_SSL_REDIRECT = HTTPS_ENABLED
SESSION_COOKIE_SECURE = HTTPS_ENABLED
CSRF_COOKIE_SECURE = HTTPS_ENABLED
SECURE_HSTS_SECONDS = 31536000 if HTTPS_ENABLED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS_ENABLED
SECURE_HSTS_PRELOAD = HTTPS_ENABLED

# Hashed + compressed static assets served by WhiteNoise (collected at image
# build time). Caddy stays a pure reverse proxy + TLS terminator.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Sentry is initialised in base.py (guarded by SENTRY_DSN); set the DSN +
# SENTRY_ENVIRONMENT in infra/.env. SENTRY_RELEASE is injected by compose.
