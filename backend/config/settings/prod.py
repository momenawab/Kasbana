"""Production settings.

Requires a real ``SECRET_KEY``, ``DATABASE_URL`` (Postgres), ``REDIS_URL`` and
the wallet/billing secrets from the contract §3.8. Served over HTTPS (the Apple
Wallet web service requires it).
"""

from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = False

# Security hardening behind the TLS-terminating proxy (Caddy/Coolify).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Sentry is wired in Phase 5; the DSN env var is read there.
