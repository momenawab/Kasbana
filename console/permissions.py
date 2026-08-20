"""Admin permission classes + the base view every admin endpoint extends.

``AdminAPIView`` centralises the three guarantees every admin endpoint needs:
admin-only auth, a role gate, and the deliberate cross-tenant access (it never
applies ``for_merchant`` scoping — that inversion lives here, not scattered).

Since Phase 12 every gate derives from the central matrix in ``console.rbac``:
the named per-domain classes below are thin ``require(...)`` aliases, and new
endpoints gate with ``require(Permission.X)`` directly. There is one source of
truth for who-can-do-what — the matrix — not scattered role checks.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from console.auth import AdminJWTAuthentication
from console.models import AdminUser
from console.rbac import Permission, role_can


class IsAdminUser(BasePermission):
    """Any authenticated, active platform admin."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, AdminUser) and request.user.is_active


class IsSuperAdmin(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return isinstance(request.user, AdminUser) and request.user.is_super_admin


class _MatrixPermission(BasePermission):
    """Grant when the active admin's role holds ``required_permission`` in the
    RBAC matrix. Super-admin holds every permission (see ``rbac.permissions_for``)."""

    required_permission: ClassVar[str] = ""

    def has_permission(self, request: Request, view: APIView) -> bool:
        admin = request.user
        return (
            isinstance(admin, AdminUser)
            and admin.is_active
            and role_can(admin.role, self.required_permission)
        )


def require(permission: str) -> type[_MatrixPermission]:
    """Build a matrix-backed permission class for ``permission`` (use inline in
    ``get_permissions`` or ``permission_classes``)."""

    return type(
        f"Require_{permission.replace('.', '_')}",
        (_MatrixPermission,),
        {"required_permission": permission},
    )


# ── Named per-domain aliases (matrix-backed) ────────────────────────────────────
# Each maps to a representative permission of its role's bucket; because Finance
# holds all finance-domain permissions (etc.), the representative check grants
# exactly the same roles as before, now sourced from the matrix. New granular
# gates should prefer ``require(Permission.X)`` over these coarse aliases.
class IsFinanceAdmin(_MatrixPermission):
    """Super-admin or Finance — billing/plans/subscriptions/revenue/promotions."""

    required_permission = Permission.BILLING_MANAGE


class IsSupportAdmin(_MatrixPermission):
    """Super-admin or Support — impersonation, support actions, notes, moderation."""

    required_permission = Permission.SUPPORT_TOOLS


class IsMarketingAdmin(_MatrixPermission):
    """Super-admin or Marketing-admin — broadcasts / announcements / promotions."""

    required_permission = Permission.ANNOUNCEMENTS_MANAGE


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
