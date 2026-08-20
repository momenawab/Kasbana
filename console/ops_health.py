"""Platform health report (Phase 14).

Real, best-effort checks — never fabricated. Each probe degrades to an honest
``{"ok": False, "detail": ...}`` instead of raising, so the ops dashboard can
render a red tile rather than 500. Kept out of the view so it's unit-testable.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)

# The queues declared in settings (contract §3.9); depth is probed per queue.
_QUEUES = ("default", "wallet", "messaging")


def _check_db() -> dict[str, Any]:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"ok": True}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "detail": str(exc)[:200]}


def _check_cache() -> dict[str, Any]:
    try:
        cache.set("ops:healthcheck", "1", 5)
        ok = cache.get("ops:healthcheck") == "1"
        backend = settings.CACHES["default"]["BACKEND"].rsplit(".", 1)[-1]
        return {"ok": ok, "backend": backend}
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "detail": str(exc)[:200]}


def _check_celery() -> dict[str, Any]:
    """Ping workers over the broker (short timeout). No workers / no broker is a
    truthful 'unreachable', not an error tile crash."""
    try:
        from config.celery import app

        replies = app.control.ping(timeout=0.5) or []
        workers = sorted(k for reply in replies for k in reply)
        return {"ok": bool(workers), "workers": workers}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)[:200]}


def _queue_depths() -> dict[str, Any]:
    """Best-effort per-queue backlog from the Redis broker; unavailable → null."""
    try:
        import redis  # provided by the redis dependency

        client = redis.Redis.from_url(str(settings.CELERY_BROKER_URL))
        return {q: int(client.llen(q)) for q in _QUEUES}
    except Exception as exc:
        return {"error": str(exc)[:200]}


def health_report() -> dict[str, Any]:
    db = _check_db()
    cache_status = _check_cache()
    celery = _check_celery()
    return {
        "api": {"ok": True},
        "database": db,
        "cache": cache_status,
        "celery": celery,
        "queues": _queue_depths(),
        "sentry": {"configured": bool(getattr(settings, "SENTRY_DSN", ""))},
        # Overall is green only when the hard dependencies are up (Celery workers
        # may legitimately be absent in some envs, so they don't gate 'healthy').
        "healthy": bool(db["ok"] and cache_status["ok"]),
    }
