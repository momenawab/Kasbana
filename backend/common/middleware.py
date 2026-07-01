"""Request middleware that attaches the caller's StaffUser as ``request.staff``.

Phase 2's loyalty views read ``request.staff`` / ``request.staff.location``
(contract §5). Because ``StaffUser.user`` is one-to-one, the staff profile is
unambiguous for an authenticated user. Anonymous/public requests get ``None``.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class StaffContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.staff = None  # type: ignore[attr-defined]
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
