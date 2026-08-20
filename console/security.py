"""Admin session lifecycle, brute-force lockout, and step-up freshness (Phase 15).

Kept apart from token minting (``console.auth``) so the policy — how many
failures lock an account, how long a step-up proof stays fresh — lives in one
readable place. Windows are generous defaults suited to an internal tool; tune
via the module constants if needed.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.utils import timezone
from rest_framework.request import Request

from console.audit import client_ip
from console.models import AdminSession, AdminUser


def token_sid(request: Request) -> str | None:
    """The ``sid`` claim on the caller's token, if present."""
    auth = cast(Any, getattr(request, "auth", None))
    return str(auth["sid"]) if auth is not None and auth.get("sid") else None


# Brute-force lockout policy.
LOCKOUT_THRESHOLD = 5  # consecutive password failures before a lock
LOCKOUT_MINUTES = 15  # how long the account stays locked

# Step-up: a sensitive action needs a credential proof this recent.
STEP_UP_MINUTES = 5


# ── brute-force lockout ─────────────────────────────────────────────────────
def is_locked(admin: AdminUser) -> bool:
    return admin.locked_until is not None and admin.locked_until > timezone.now()


def register_failed_login(admin: AdminUser) -> None:
    """Count a failed password attempt; lock the account past the threshold."""
    admin.failed_login_count += 1
    if admin.failed_login_count >= LOCKOUT_THRESHOLD:
        admin.locked_until = timezone.now() + timedelta(minutes=LOCKOUT_MINUTES)
    admin.save(update_fields=["failed_login_count", "locked_until", "updated_at"])


def reset_lockout(admin: AdminUser) -> None:
    """Clear the failure counter + any lock (called on a successful login)."""
    if admin.failed_login_count or admin.locked_until:
        admin.failed_login_count = 0
        admin.locked_until = None
        admin.save(update_fields=["failed_login_count", "locked_until", "updated_at"])


# ── sessions ────────────────────────────────────────────────────────────────
def create_session(admin: AdminUser, request: Request) -> AdminSession:
    now = timezone.now()
    return AdminSession.objects.create(
        admin=admin,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
        ip=client_ip(request),
        last_seen_at=now,
        last_auth_at=now,
    )


def touch_session(session: AdminSession) -> None:
    session.last_seen_at = timezone.now()
    session.save(update_fields=["last_seen_at"])


def revoke_session(session: AdminSession) -> None:
    if not session.revoked:
        session.revoked = True
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked", "revoked_at"])


def revoke_all_sessions(admin: AdminUser, *, except_id: str | None = None) -> int:
    """Revoke every active session for ``admin`` ("log out everywhere").

    Returns the number revoked. ``except_id`` keeps the caller's own session
    alive (so "log out my *other* devices" doesn't sign the caller out too).
    """
    qs = admin.sessions.filter(revoked=False)
    if except_id is not None:
        qs = qs.exclude(id=except_id)
    return qs.update(revoked=True, revoked_at=timezone.now())


def current_session(request: Request, admin: AdminUser) -> AdminSession | None:
    """The active session behind the caller's token (via its ``sid`` claim)."""
    sid = token_sid(request)
    if not sid:
        return None
    return AdminSession.objects.filter(id=sid, admin=admin, revoked=False).first()


# ── step-up freshness ────────────────────────────────────────────────────────
def step_up_fresh(session: AdminSession) -> bool:
    """Whether this session proved credentials recently enough for a sensitive
    action."""
    if session.last_auth_at is None:
        return False
    return session.last_auth_at > timezone.now() - timedelta(minutes=STEP_UP_MINUTES)


def mark_step_up(session: AdminSession) -> None:
    session.last_auth_at = timezone.now()
    session.save(update_fields=["last_auth_at"])
