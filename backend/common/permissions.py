"""RBAC permissions (contract §3.2 Role enum).

Role hierarchy: OWNER > ADMIN > SCANNER. Every permission resolves the caller's
StaffUser (binding them to a merchant) and checks their role meets the minimum.
"""

from __future__ import annotations

from typing import ClassVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from common.middleware import resolve_staff
from core.enums import Role

# Higher number = more authority.
ROLE_RANK: dict[str, int] = {
    Role.SCANNER: 1,
    Role.ADMIN: 2,
    Role.OWNER: 3,
}


class HasMerchantRole(BasePermission):
    """Grant access when the caller's staff role meets ``min_role``."""

    min_role: ClassVar[str] = Role.SCANNER

    def has_permission(self, request: Request, view: APIView) -> bool:
        staff = resolve_staff(request)
        if staff is None:
            return False
        return ROLE_RANK.get(getattr(staff, "role", ""), 0) >= ROLE_RANK[self.min_role]


class IsScannerOrAbove(HasMerchantRole):
    """Any active staff member of a merchant (scanner, admin, owner)."""

    min_role = Role.SCANNER


class IsAdminOrAbove(HasMerchantRole):
    min_role = Role.ADMIN


class IsOwner(HasMerchantRole):
    min_role = Role.OWNER
