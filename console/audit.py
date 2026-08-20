"""Audit writer — the one call every mutating admin action makes.

``record(request, action, ...)`` snapshots the actor + client and appends an
``AdminAuditLog`` row. Kept tiny and dependency-free so any view can call it.
"""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request

from console.models import AdminAuditLog, AdminUser


def client_ip(request: Request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record(
    request: Request,
    action: str,
    *,
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> AdminAuditLog:
    """Append an audit row for the admin behind ``request``."""
    actor = request.user if isinstance(request.user, AdminUser) else None
    return AdminAuditLog.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", ""),
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        metadata=metadata or {},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
    )
