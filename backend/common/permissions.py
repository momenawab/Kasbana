"""RBAC permissions (contract §3.2 Role enum).

Two role shapes coexist:

- **Hierarchical** — OWNER > ADMIN > {SCANNER, DESIGNER, MARKETING}. The
  ``*OrAbove`` classes use ``ROLE_RANK``; the specialised lateral roles sit at
  the base rank so ``IsAdminOrAbove`` / ``IsOwner`` exclude them by default
  (a safe default: a view not migrated to a capability stays admin/owner-only).
- **Lateral capabilities** — DESIGNER owns cards/branding, MARKETING owns
  engagement (campaigns/customers/analytics). The ``Can*`` classes grant those
  areas to the lateral role *plus* the admins/owner who can do everything.

Every permission resolves the caller's StaffUser (binding them to a merchant).
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from common.middleware import resolve_staff
from core.enums import Role

# Higher number = more authority. The lateral roles (designer/marketing) rank at
# the base so the hierarchical checks below treat them like a scanner — their
# extra access comes only from the capability classes, never from rank.
ROLE_RANK: dict[str, int] = {
    Role.SCANNER: 1,
    Role.DESIGNER: 1,
    Role.MARKETING: 1,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}


class HasMerchantRole(BasePermission):
    """Grant access when the caller's staff role meets ``min_role`` by rank."""

    min_role: ClassVar[str] = Role.SCANNER

    def has_permission(self, request: Request, view: APIView) -> bool:
        staff = resolve_staff(request)
        if staff is None:
            return False
        return ROLE_RANK.get(getattr(staff, "role", ""), 0) >= ROLE_RANK[self.min_role]


class IsScannerOrAbove(HasMerchantRole):
    """Any active staff member of a merchant — everyone can scan."""

    min_role = Role.SCANNER


class IsAdminOrAbove(HasMerchantRole):
    """Owner or Admin only — excludes the lateral designer/marketing roles."""

    min_role = Role.ADMIN


class IsOwner(HasMerchantRole):
    min_role = Role.OWNER


# ── Lateral capability roles ──────────────────────────────────────────────────
# Owner + Admin can do everything, so they're in every set; the specialised role
# is added to its own area.
_CARDS_ROLES: set[str] = {Role.OWNER, Role.ADMIN, Role.DESIGNER}
_ENGAGE_ROLES: set[str] = {Role.OWNER, Role.ADMIN, Role.MARKETING}
_INSIGHTS_ROLES: set[str] = {Role.OWNER, Role.ADMIN, Role.MARKETING, Role.DESIGNER}


class _RoleSet(BasePermission):
    """Grant access when the caller's role is in ``roles``."""

    roles: ClassVar[set[str]] = set()

    def has_permission(self, request: Request, view: APIView) -> bool:
        staff = resolve_staff(request)
        return staff is not None and getattr(staff, "role", "") in self.roles


class CanManageCards(_RoleSet):
    """Card design + branding — Owner, Admin, Designer."""

    roles = _CARDS_ROLES


class CanEngage(_RoleSet):
    """Campaigns, customers, messaging — Owner, Admin, Marketing."""

    roles = _ENGAGE_ROLES


class CanViewInsights(_RoleSet):
    """Overview + analytics — Owner, Admin, Marketing, Designer (not Scanner)."""

    roles = _INSIGHTS_ROLES
