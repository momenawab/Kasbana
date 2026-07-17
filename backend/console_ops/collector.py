"""Narrow client for the internal host collector. Never falls back to shell."""

from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings


def snapshot(*, include_logs: bool = False) -> dict[str, Any]:
    token = getattr(settings, "OPS_COLLECTOR_TOKEN", "")
    if not token:
        return {"available": False, "detail": "collector token is not configured"}
    try:
        response = httpx.get(
            getattr(settings, "OPS_COLLECTOR_URL", "http://ops-collector:9800/v1/snapshot"),
            params={"include_logs": str(include_logs).lower()},
            headers={"X-Ops-Collector-Token": token},
            timeout=3.0,
        )
        response.raise_for_status()
        return {"available": True, **response.json()}
    except httpx.HTTPError as exc:
        return {"available": False, "detail": str(exc)[:200]}
