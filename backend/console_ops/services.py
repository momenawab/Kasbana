"""Composition root for snapshots, dashboard responses, alert state and quiet hours."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from console import ops_health

from . import collector
from .health import evaluate
from .models import OpsAlert, OpsConfiguration, OpsSnapshot

SNAPSHOT_CACHE_KEY = "stampn_ops:dashboard"


def _database_metrics() -> dict[str, Any]:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM pg_stat_activity")
            connections = cur.fetchone()[0]
            cur.execute("SELECT pg_database_size(current_database())")
            size = cur.fetchone()[0]
        return {"connected": True, "connections": connections, "size_bytes": size}
    except Exception as exc:
        return {"connected": False, "detail": str(exc)[:200]}


def _business_metrics() -> dict[str, int]:
    # Imported lazily so the module stays importable during migrations.
    from core.models import CustomerCard, Merchant, Redemption, StampLedger

    today = timezone.localdate()
    return {
        "active_businesses": Merchant.objects.count(),
        "new_businesses": Merchant.objects.filter(created_at__date=today).count(),
        "customers": CustomerCard.objects.filter(created_at__date=today).count(),
        "stamps": StampLedger.objects.filter(created_at__date=today).count(),
        "redemptions": Redemption.objects.filter(created_at__date=today).count(),
        "online_users": 0,
    }  # exact online users requires a future heartbeat, never guessed.


def _alerts(
    payload: dict[str, Any], thresholds: dict[str, float], penalties: list[dict[str, str]]
) -> None:
    now = timezone.now()
    open_fingerprints: set[str] = set()
    for penalty in penalties:
        fingerprint = hashlib.sha256(penalty["reason"].encode()).hexdigest()[:40]
        open_fingerprints.add(fingerprint)
        alert, created = OpsAlert.objects.get_or_create(
            fingerprint=fingerprint,
            defaults={
                "severity": penalty["severity"],
                "status": "open",
                "title": "Stampn Ops health alert",
                "detail": penalty["reason"],
                "first_seen_at": now,
                "last_seen_at": now,
            },
        )
        if not created:
            alert.severity = penalty["severity"]
            alert.status = "open"
            alert.detail = penalty["reason"]
            alert.last_seen_at = now
            alert.occurrences += 1
            alert.resolved_at = None
            alert.save(
                update_fields=[
                    "severity",
                    "status",
                    "detail",
                    "last_seen_at",
                    "occurrences",
                    "resolved_at",
                    "updated_at",
                ]
            )
    OpsAlert.objects.filter(status="open").exclude(fingerprint__in=open_fingerprints).update(
        status="resolved", resolved_at=now
    )


def take_snapshot(*, include_logs: bool = False) -> dict[str, Any]:
    config = OpsConfiguration.current()
    host = collector.snapshot(include_logs=include_logs)
    score, status, penalties = evaluate(host, config.thresholds)
    dependencies = ops_health.health_report()
    payload = {
        **host,
        "api": dependencies["api"],
        "database": _database_metrics(),
        "redis": {"connected": dependencies["cache"]["ok"]},
        "queues": dependencies["queues"],
        "business": _business_metrics(),
        "penalties": penalties,
    }
    observed = timezone.now()
    OpsSnapshot.objects.create(
        observed_at=observed, health_score=score, status=status, payload=payload
    )
    _alerts(payload, config.thresholds, penalties)
    dashboard = {
        "observed_at": observed.isoformat(),
        "health_score": score,
        "status": status,
        **payload,
    }
    cache.set(SNAPSHOT_CACHE_KEY, dashboard, 90)
    return dashboard


def dashboard(*, refresh: bool = False) -> dict[str, Any]:
    cached = None if refresh else cache.get(SNAPSHOT_CACHE_KEY)
    if cached:
        return cached
    latest = OpsSnapshot.objects.order_by("-observed_at").first()
    if latest and latest.observed_at >= timezone.now() - timedelta(minutes=2):
        return {
            "observed_at": latest.observed_at.isoformat(),
            "health_score": latest.health_score,
            "status": latest.status,
            **latest.payload,
        }
    return take_snapshot()


def in_quiet_hours(config: OpsConfiguration, now: datetime | None = None) -> bool:
    if not config.quiet_hours_start or not config.quiet_hours_end:
        return False
    current = (now or timezone.localtime()).time()
    start, end = config.quiet_hours_start, config.quiet_hours_end
    return start <= current < end if start < end else current >= start or current < end
