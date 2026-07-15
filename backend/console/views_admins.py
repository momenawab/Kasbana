"""Admin-team management + RBAC matrix endpoints (Phase 12).

Managing the admin team is the sharpest privilege in the console, so every
endpoint here is gated to ``ADMINS_MANAGE`` (super-admin only, per the matrix).
Guardrail: the last active super-admin can't be demoted or deactivated (whether
that's someone else or yourself), so the platform can never be locked out of
admin management.
"""

from __future__ import annotations

import secrets

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import (
    ALL_PERMISSIONS,
    MFA_REQUIRED_ROLES,
    Permission,
    permissions_for,
)
from console.serializers_admins import (
    AdminActivitySerializer,
    AdminInviteResultSerializer,
    AdminInviteSerializer,
    AdminUpdateSerializer,
    AdminUserSerializer,
)


def _active_super_admin_count(exclude_id: str | None = None) -> int:
    qs = AdminUser.objects.filter(role=AdminRole.SUPER_ADMIN, is_active=True)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs.count()


class AdminListCreateView(AdminAPIView):
    """GET /admins — list the team. POST /admins — invite a new admin."""

    permission_classes = [IsAdminUser, require(Permission.ADMINS_MANAGE)]

    @extend_schema(responses=AdminUserSerializer(many=True))
    def get(self, request: Request) -> Response:
        admins = AdminUser.objects.all()
        return Response(AdminUserSerializer(admins, many=True).data)

    @extend_schema(request=AdminInviteSerializer, responses=AdminInviteResultSerializer)
    def post(self, request: Request) -> Response:
        body = AdminInviteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        email = body.validated_data["email"].strip().lower()

        duplicate = Response(
            {"error": {"code": "CONFLICT", "message": "An admin with this email exists."}},
            status=409,
        )
        if AdminUser.objects.filter(email__iexact=email).exists():
            return duplicate

        temp_password = secrets.token_urlsafe(12)
        admin = AdminUser(
            email=email,
            name=body.validated_data.get("name", ""),
            role=body.validated_data["role"],
            is_active=True,
        )
        admin.set_password(temp_password)
        try:
            admin.save()
        except IntegrityError:
            # Concurrent invite of the same email won the race between the check
            # above and this save — the unique constraint fired. Same 409, not a 500.
            return duplicate

        audit.record(
            request,
            "admin.invite",
            target_type="admin",
            target_id=str(admin.id),
            metadata={"email": admin.email, "role": admin.role},
        )
        return Response(
            AdminInviteResultSerializer({"admin": admin, "temporary_password": temp_password}).data,
            status=201,
        )


class AdminDetailView(AdminAPIView):
    """PATCH /admins/{id} — change role and/or active state (guarded + audited)."""

    permission_classes = [IsAdminUser, require(Permission.ADMINS_MANAGE)]

    @extend_schema(request=AdminUpdateSerializer, responses=AdminUserSerializer)
    def patch(self, request: Request, admin_id: str) -> Response:
        target = get_object_or_404(AdminUser, pk=admin_id)
        body = AdminUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        new_role = data.get("role", target.role)
        new_active = data.get("is_active", target.is_active)

        # Last-active-super-admin protection: any change that would drop the count
        # of active super-admins to zero is blocked — this covers demoting or
        # deactivating the last super (whether that's someone else or yourself),
        # so the platform can never be locked out of admin management.
        losing_super = target.role == AdminRole.SUPER_ADMIN and (
            new_role != AdminRole.SUPER_ADMIN or not new_active
        )
        if losing_super and _active_super_admin_count(exclude_id=str(target.id)) == 0:
            return Response(
                {
                    "error": {
                        "code": "CONFLICT",
                        "message": "Can't remove the last active super-admin.",
                    }
                },
                status=409,
            )

        before = {"role": target.role, "is_active": target.is_active}
        target.role = new_role
        target.is_active = new_active
        target.save(update_fields=["role", "is_active", "updated_at"])

        audit.record(
            request,
            "admin.update",
            target_type="admin",
            target_id=str(target.id),
            metadata={
                "reason": data["reason"],
                "before": before,
                "after": {"role": target.role, "is_active": target.is_active},
            },
        )
        return Response(AdminUserSerializer(target).data)


class AdminActivityView(AdminAPIView):
    """GET /admins/{id}/activity — that admin's recent audited actions."""

    permission_classes = [IsAdminUser, require(Permission.ADMINS_MANAGE)]

    @extend_schema(responses=AdminActivitySerializer(many=True))
    def get(self, request: Request, admin_id: str) -> Response:
        target = get_object_or_404(AdminUser, pk=admin_id)
        logs = AdminAuditLog.objects.filter(actor=target)[:50]
        return Response(AdminActivitySerializer(logs, many=True).data)


class AdminResetMfaView(AdminAPIView):
    """POST /admins/{id}/reset-mfa — clear an admin's MFA (Phase 15 recovery).

    The path back when an admin loses their authenticator: a super-admin resets
    it, and the target is forced to re-enrol on their next login (privileged
    roles) or is simply MFA-less again. Also revokes the target's sessions so a
    compromised device can't keep a live token. Super-admin only, audited.
    """

    permission_classes = [IsAdminUser, require(Permission.ADMINS_MANAGE)]

    @extend_schema(request=None, responses=AdminUserSerializer)
    def post(self, request: Request, admin_id: str) -> Response:
        from console import security

        target = get_object_or_404(AdminUser, pk=admin_id)
        target.mfa_enabled = False
        target.mfa_secret = ""
        target.save(update_fields=["mfa_enabled", "mfa_secret", "updated_at"])
        revoked = security.revoke_all_sessions(target)
        audit.record(
            request,
            "admin.reset_mfa",
            target_type="admin",
            target_id=str(target.id),
            metadata={"email": target.email, "sessions_revoked": revoked},
        )
        return Response(AdminUserSerializer(target).data)


class RbacMatrixView(AdminAPIView):
    """GET /rbac/matrix — the permission matrix (read-only reference).

    Open to any admin: it's reference material (which role can do what), not
    secret, and the Admin Team screen renders it so operators understand the gates.
    """

    @extend_schema(responses=None)
    def get(self, request: Request) -> Response:
        return Response(
            {
                "permissions": sorted(ALL_PERMISSIONS),
                "roles": [
                    {
                        "role": role,
                        "label": AdminRole(role).label,
                        "permissions": sorted(permissions_for(role)),
                        "mfa_required": role in MFA_REQUIRED_ROLES,
                    }
                    for role in AdminRole.values
                ],
            }
        )
