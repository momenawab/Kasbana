"""Admin auth + session endpoints (Phase 1 + Phase 15 hardening).

``/auth/login`` · ``/auth/mfa/verify`` · ``/auth/refresh`` · ``/auth/step-up`` ·
``/auth/mfa/setup`` · ``/auth/mfa/confirm`` · ``/auth/sessions`` · ``/me``.

Login is email+password, then a TOTP gate: an admin with MFA enabled must enter
a code; a privileged admin who hasn't enrolled yet is pushed through enrolment
(forced, but never locked out — see the ``mfa_setup`` branch). Brute-force
lockout guards the password step; every session is tracked so it can be listed
and revoked ("log out everywhere").
"""

from __future__ import annotations

from typing import cast

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from console import mfa, security
from console.audit import client_ip
from console.auth import (
    SCOPE_MFA_CHALLENGE,
    SCOPE_MFA_SETUP,
    AdminJWTAuthentication,
    issue_admin_tokens,
    issue_pending_token,
    refresh_admin_access,
    resolve_pending,
)
from console.models import AdminAuditLog, AdminUser
from console.permissions import AdminAPIView
from console.rbac import mfa_required
from console.serializers import (
    AdminLoginResultSerializer,
    AdminLoginSerializer,
    AdminMeSerializer,
    AdminRefreshSerializer,
    AdminSessionSerializer,
    AdminTokenSerializer,
    MfaConfirmSerializer,
    MfaSetupSerializer,
    MfaVerifySerializer,
    StepUpSerializer,
)


def _audit(admin: AdminUser | None, action: str, request: Request, **meta: object) -> None:
    AdminAuditLog.objects.create(
        actor=admin,
        actor_email=getattr(admin, "email", ""),
        action=action,
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:256],
        metadata=meta or {},
    )


class AdminLoginView(APIView):
    """POST /auth/login — email+password → tokens, or an MFA gate."""

    # The admin authenticator returns anonymous when no token is sent (so login
    # is reachable) but supplies a WWW-Authenticate header, keeping credential
    # failures a proper 401 (DRF downgrades to 403 when no authenticator exists).
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "admin_auth"

    @extend_schema(request=AdminLoginSerializer, responses=AdminLoginResultSerializer)
    def post(self, request: Request) -> Response:
        body = AdminLoginSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        admin = AdminUser.objects.filter(email__iexact=body.validated_data["email"]).first()

        # Locked accounts are refused before the password check so a lockout can't
        # be walked around by guessing; a generic message avoids leaking state.
        if admin is not None and security.is_locked(admin):
            _audit(admin, "admin.login_locked", request)
            raise AuthenticationFailed("Account temporarily locked. Try again later.")

        ok = bool(
            admin and admin.is_active and admin.check_password(body.validated_data["password"])
        )
        if not ok:
            if admin is not None and admin.is_active:
                security.register_failed_login(admin)
            raise AuthenticationFailed("Invalid credentials.")

        assert admin is not None  # narrowed by ok
        security.reset_lockout(admin)

        # Password is correct. Gate on MFA before issuing full tokens.
        if admin.mfa_enabled:
            return Response(
                {
                    "status": "mfa_required",
                    "pending_token": issue_pending_token(admin, SCOPE_MFA_CHALLENGE),
                }
            )
        if mfa_required(admin.role):
            # Privileged role without MFA yet → forced enrolment (never locked out).
            secret = mfa.new_secret()
            admin.mfa_secret = secret  # stored unconfirmed; enabled only on verify
            admin.save(update_fields=["mfa_secret", "updated_at"])
            uri = mfa.provisioning_uri(secret, admin.email)
            return Response(
                {
                    "status": "mfa_setup",
                    "pending_token": issue_pending_token(admin, SCOPE_MFA_SETUP),
                    "otpauth_uri": uri,
                    "secret": secret,
                    "qr": mfa.qr_data_uri(uri),
                }
            )

        # No MFA required for this role — issue full tokens directly.
        return Response({"status": "ok", **self._finish_login(admin, request)})

    def _finish_login(self, admin: AdminUser, request: Request) -> dict[str, str]:
        admin.last_login_at = timezone.now()
        admin.last_login_ip = client_ip(request)
        admin.save(update_fields=["last_login_at", "last_login_ip", "updated_at"])
        session = security.create_session(admin, request)
        _audit(admin, "admin.login", request, session_id=str(session.id))
        return issue_admin_tokens(admin, session)


class MfaVerifyView(AdminLoginView):
    """POST /auth/mfa/verify — complete a login: pending token + TOTP → tokens.

    Handles both the ``mfa_challenge`` (already enrolled) and ``mfa_setup``
    (enrolling now — flips ``mfa_enabled`` on first valid code) flows.
    """

    @extend_schema(request=MfaVerifySerializer, responses=AdminTokenSerializer)
    def post(self, request: Request) -> Response:
        body = MfaVerifySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin, scope = resolve_pending(body.validated_data["pending_token"])

        if not mfa.verify(admin.mfa_secret, body.validated_data["code"]):
            raise AuthenticationFailed("Invalid authentication code.")

        if scope == SCOPE_MFA_SETUP and not admin.mfa_enabled:
            admin.mfa_enabled = True
            admin.save(update_fields=["mfa_enabled", "updated_at"])
            _audit(admin, "admin.mfa_enrolled", request)

        return Response({"status": "ok", **self._finish_login(admin, request)})


class AdminRefreshView(APIView):
    """POST /auth/refresh — rotate the refresh token → a fresh pair."""

    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_scope = "admin_auth"

    @extend_schema(request=AdminRefreshSerializer, responses=AdminTokenSerializer)
    def post(self, request: Request) -> Response:
        body = AdminRefreshSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(refresh_admin_access(body.validated_data["refresh"]))


class AdminMeView(AdminAPIView):
    """GET /me — the logged-in admin's profile."""

    @extend_schema(responses=AdminMeSerializer)
    def get(self, request: Request) -> Response:
        from console.rbac import permissions_for

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


class MfaSetupView(AdminAPIView):
    """POST /auth/mfa/setup — voluntarily start MFA enrolment (already logged in).

    Returns fresh provisioning data; ``/auth/mfa/confirm`` completes it. Useful
    for non-privileged roles that want MFA even though it isn't forced.
    """

    @extend_schema(request=None, responses=MfaSetupSerializer)
    def post(self, request: Request) -> Response:
        admin = cast(AdminUser, request.user)
        secret = mfa.new_secret()
        admin.mfa_secret = secret
        admin.save(update_fields=["mfa_secret", "updated_at"])
        uri = mfa.provisioning_uri(secret, admin.email)
        return Response({"otpauth_uri": uri, "secret": secret, "qr": mfa.qr_data_uri(uri)})


class MfaConfirmView(AdminAPIView):
    """POST /auth/mfa/confirm — finish voluntary enrolment with a TOTP code."""

    @extend_schema(request=MfaConfirmSerializer, responses=None)
    def post(self, request: Request) -> Response:
        admin = cast(AdminUser, request.user)
        body = MfaConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if not admin.mfa_secret or not mfa.verify(admin.mfa_secret, body.validated_data["code"]):
            raise ValidationError({"code": "Invalid authentication code."})
        if not admin.mfa_enabled:
            admin.mfa_enabled = True
            admin.save(update_fields=["mfa_enabled", "updated_at"])
            _audit(admin, "admin.mfa_enrolled", request)
        return Response({"enabled": True})


class StepUpView(AdminAPIView):
    """POST /auth/step-up — re-prove credentials to unlock a sensitive action.

    Refreshes the session's ``last_auth_at``; sensitive endpoints require it to
    be recent. Requires the password, plus a TOTP code when MFA is enabled.
    """

    throttle_scope = "admin_auth"

    @extend_schema(request=StepUpSerializer, responses=None)
    def post(self, request: Request) -> Response:
        admin = cast(AdminUser, request.user)
        body = StepUpSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if not admin.check_password(body.validated_data["password"]):
            raise AuthenticationFailed("Invalid credentials.")
        if admin.mfa_enabled and not mfa.verify(
            admin.mfa_secret, body.validated_data.get("code", "")
        ):
            raise AuthenticationFailed("Invalid authentication code.")

        session = security.current_session(request, admin)
        if session is not None:
            security.mark_step_up(session)
        _audit(admin, "admin.step_up", request)
        return Response({"ok": True})


class AdminSessionListView(AdminAPIView):
    """GET /auth/sessions — this admin's active sessions/devices.
    DELETE /auth/sessions — "log out everywhere" (keeps the current session)."""

    @extend_schema(responses=AdminSessionSerializer(many=True))
    def get(self, request: Request) -> Response:
        admin = cast(AdminUser, request.user)
        current_sid = security.token_sid(request)
        rows = [
            {
                "id": s.id,
                "user_agent": s.user_agent,
                "ip": s.ip,
                "created_at": s.created_at,
                "last_seen_at": s.last_seen_at,
                "current": str(s.id) == current_sid,
            }
            for s in admin.sessions.filter(revoked=False)
        ]
        return Response(AdminSessionSerializer(rows, many=True).data)

    @extend_schema(request=None, responses={200: None})
    def delete(self, request: Request) -> Response:
        admin = cast(AdminUser, request.user)
        current_sid = security.token_sid(request)
        count = security.revoke_all_sessions(admin, except_id=current_sid)
        _audit(admin, "admin.logout_everywhere", request, revoked=count)
        return Response({"revoked": count})


class AdminSessionRevokeView(AdminAPIView):
    """DELETE /auth/sessions/{id} — revoke one specific session/device."""

    @extend_schema(request=None, responses={200: None})
    def delete(self, request: Request, session_id: str) -> Response:
        admin = cast(AdminUser, request.user)
        session = admin.sessions.filter(id=session_id, revoked=False).first()
        if session is None:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "No such active session."}}, status=404
            )
        security.revoke_session(session)
        _audit(admin, "admin.session_revoke", request, session_id=str(session.id))
        return Response({"revoked": 1})
