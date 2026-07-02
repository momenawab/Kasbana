"""Admin auth + session endpoints (Phase 1).

``/api/admin/v1/auth/login`` · ``/auth/refresh`` · ``/me``. Login is
email+password → admin JWT pair (MFA slots in at Phase 15). Everything else in
the console mounts under the same ``/api/admin/v1`` prefix in later phases.
"""

from __future__ import annotations

from typing import cast

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from console.audit import client_ip
from console.auth import AdminJWTAuthentication, issue_admin_tokens, refresh_admin_access
from console.models import AdminAuditLog, AdminUser
from console.permissions import AdminAPIView
from console.serializers import (
    AdminAccessSerializer,
    AdminLoginSerializer,
    AdminMeSerializer,
    AdminRefreshSerializer,
    AdminTokenSerializer,
)


class AdminLoginView(APIView):
    """POST /api/admin/v1/auth/login — email+password → admin token pair."""

    # The admin authenticator returns anonymous when no token is sent (so login
    # is reachable) but supplies a WWW-Authenticate header, keeping credential
    # failures a proper 401 (DRF downgrades to 403 when no authenticator exists).
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "admin_auth"

    @extend_schema(request=AdminLoginSerializer, responses=AdminTokenSerializer)
    def post(self, request: Request) -> Response:
        body = AdminLoginSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        admin = AdminUser.objects.filter(email__iexact=body.validated_data["email"]).first()
        # Constant-ish: still run check_password against a real hash when the admin
        # exists; a generic error either way so we don't leak which emails exist.
        ok = bool(
            admin and admin.is_active and admin.check_password(body.validated_data["password"])
        )
        if not ok:
            from rest_framework.exceptions import AuthenticationFailed

            raise AuthenticationFailed("Invalid credentials.")

        assert admin is not None  # narrowed by ok
        admin.last_login_at = timezone.now()
        admin.last_login_ip = client_ip(request)
        admin.save(update_fields=["last_login_at", "last_login_ip", "updated_at"])
        AdminAuditLog.objects.create(
            actor=admin,
            actor_email=admin.email,
            action="admin.login",
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
        )
        return Response(issue_admin_tokens(admin))


class AdminRefreshView(APIView):
    """POST /api/admin/v1/auth/refresh — new access token from a refresh token."""

    # The admin authenticator returns anonymous when no token is sent (so login
    # is reachable) but supplies a WWW-Authenticate header, keeping credential
    # failures a proper 401 (DRF downgrades to 403 when no authenticator exists).
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "admin_auth"

    @extend_schema(request=AdminRefreshSerializer, responses=AdminAccessSerializer)
    def post(self, request: Request) -> Response:
        body = AdminRefreshSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response({"access": refresh_admin_access(body.validated_data["refresh"])})


class AdminMeView(AdminAPIView):
    """GET /api/admin/v1/me — the logged-in admin's profile."""

    @extend_schema(responses=AdminMeSerializer)
    def get(self, request: Request) -> Response:
        from console.rbac import mfa_required, permissions_for

        admin = cast(AdminUser, request.user)  # AdminAPIView guarantees this
        return Response(
            AdminMeSerializer(
                {
                    "id": admin.id,
                    "email": admin.email,
                    "name": admin.name,
                    "role": admin.role,
                    "mfa_enabled": admin.mfa_enabled,
                    "mfa_required": mfa_required(admin.role),
                    "permissions": sorted(permissions_for(admin.role)),
                }
            ).data
        )
