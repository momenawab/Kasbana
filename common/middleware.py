"""Request middleware that attaches the caller's StaffUser as ``request.staff``.

Phase 2's loyalty views read ``request.staff`` / ``request.staff.location``
(contract §5). Because ``StaffUser.user`` is one-to-one, the staff profile is
unambiguous for an authenticated user. Anonymous/public requests get ``None``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from common.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """Give every request a correlation id: reuse an inbound ``X-Request-ID``
    (e.g. from Caddy) or mint one, expose it to logging via a ContextVar, tag the
    Sentry scope, and echo it on the response so a client can quote it in a bug
    report. Placed first so it wraps every other middleware's logging."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        # Cap an attacker-supplied header so it can't bloat every log line.
        request_id = incoming[:64] if incoming else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.request_id = request_id  # type: ignore[attr-defined]

        # Tie Sentry issues to the same id, best-effort (no-op without the SDK).
        try:
            import sentry_sdk

            sentry_sdk.set_tag("request_id", request_id)
        except Exception:  # pragma: no cover - Sentry absent/uninitialised
            pass

        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response


class StaffContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.staff = None  # type: ignore[attr-defined]
        return self.get_response(request)


class MaintenanceModeMiddleware:
    """Return 503 for merchant-facing API traffic while maintenance mode is on
    (Phase 14). The admin console (``/api/admin/``) and the health check are
    always allowed, so operators can toggle it back off and deploys still verify.

    The state is read from a briefly-cached PlatformSetting (see
    ``console.flags.maintenance_state``), so the per-request cost is a cache hit,
    not a DB query, when nothing is wrong.
    """

    # Prefixes that stay reachable during maintenance.
    ALLOW_PREFIXES = ("/api/admin/", "/api/health")

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path
        if path.startswith("/api/") and not path.startswith(self.ALLOW_PREFIXES):
            from console.flags import maintenance_state

            state = maintenance_state()
            if state["enabled"]:
                message = state["message"] or "Stampn is temporarily down for maintenance."
                response = JsonResponse(
                    {"error": {"code": "MAINTENANCE", "message": message}}, status=503
                )
                response["Retry-After"] = "300"
                return response
        return self.get_response(request)


def resolve_staff(request: HttpRequest) -> object | None:
    """Resolve and cache ``request.staff`` lazily.

    DRF authenticates inside the view (after middleware), so ``request.user`` is
    only reliable there. Views/permissions call this to populate ``request.staff``.
    """
    cached = getattr(request, "staff", None)
    if cached is not None:
        return cached

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None

    # Imported lazily to avoid app-registry import order issues.
    from core.models import StaffUser

    staff = (
        StaffUser.objects.filter(user=user, is_active=True)
        .select_related("merchant", "location")
        .first()
    )
    request.staff = staff  # type: ignore[attr-defined]
    return staff
