"""Admin permission classes + the base view every admin endpoint extends.

``AdminAPIView`` centralises the three guarantees every admin endpoint needs:
admin-only auth, a role gate, and the deliberate cross-tenant access (it never
applies ``for_merchant`` scoping — that inversion lives here, not scattered).
The full per-role permission matrix arrives in Phase 12; for now roles are
checked with simple class attributes.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from console.auth import AdminJWTAuthentication
from console.enums import AdminRole
from console.models import AdminUser


class IsAdminUser(BasePermission):
    """Any authenticated, active platform admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, AdminUser) and request.user.is_active


class IsSuperAdmin(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, AdminUser) and request.user.is_super_admin


class IsFinanceAdmin(BasePermission):
    """Grant to Super-admin or Finance — gates billing-impacting mutations
    (e.g. plan catalogue edits, Phase 3) without waiting for the full
    per-role permission matrix (Phase 12)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        admin = request.user
        return (
            isinstance(admin, AdminUser)
            and admin.is_active
            and (admin.is_super_admin or admin.role == AdminRole.FINANCE)
        )


class HasAdminRole(BasePermission):
    """Grant when the admin's role is in ``view.allowed_roles`` (super always ok)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        admin = request.user
        if not isinstance(admin, AdminUser) or not admin.is_active:
            return False
        allowed = getattr(view, "allowed_roles", None)
        if allowed is None:  # no explicit gate -> any admin
            return True
        return admin.role in allowed or admin.is_super_admin


class AdminAPIView(APIView):
    """Base for all ``/api/admin/v1`` endpoints.

    - authenticates ONLY via the admin JWT boundary;
    - requires an active admin whose role satisfies ``allowed_roles`` (None = any);
    - intentionally does NO tenant scoping — admin views are cross-tenant.
    """

    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAdminUser, HasAdminRole]
    # Subclasses set this to a set/tuple of AdminRole values to restrict access.
    allowed_roles: ClassVar[set[str] | None] = None
