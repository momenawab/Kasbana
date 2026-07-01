"""Admin JWT auth — a boundary fully separate from the merchant auth.

Admin tokens carry a custom ``realm:"admin"`` claim + ``admin_id`` and NO
``user_id``. So:
- a merchant token hitting an admin endpoint fails (no ``realm:"admin"``);
- an admin token hitting a merchant endpoint fails (the default SimpleJWT auth
  looks up ``user_id``, which admin tokens lack).

We use a custom ``realm`` claim rather than the reserved JWT ``aud`` claim on
purpose — ``aud`` triggers PyJWT's audience validation and would need global
config that could affect merchant tokens. Admin endpoints use ONLY
``AdminJWTAuthentication``; merchant endpoints use ONLY the default. The two never
overlap even though they share a signing key.
"""

from __future__ import annotations

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from console.models import AdminUser

REALM_CLAIM = "realm"
ADMIN_REALM = "admin"


def issue_admin_tokens(admin: AdminUser) -> dict[str, str]:
    """Mint an ``{access, refresh}`` pair for an admin.

    Custom claims set on the refresh token are copied onto its access token by
    SimpleJWT, so both carry the ``realm`` + ``admin_id``.
    """
    refresh = RefreshToken()
    refresh[REALM_CLAIM] = ADMIN_REALM
    refresh["admin_id"] = str(admin.id)
    refresh["role"] = admin.role
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _admin_from_token(token: AccessToken | RefreshToken) -> AdminUser:
    if token.get(REALM_CLAIM) != ADMIN_REALM:
        raise AuthenticationFailed("Not an admin token.")
    admin = AdminUser.objects.filter(id=token.get("admin_id"), is_active=True).first()
    if admin is None:
        raise AuthenticationFailed("Admin account not found or inactive.")
    return admin


def refresh_admin_access(raw_refresh: str) -> str:
    """Validate a refresh token + issue a fresh access token (same claims)."""
    try:
        token = RefreshToken(raw_refresh)  # type: ignore[arg-type]  # accepts str at runtime
    except TokenError as exc:
        raise AuthenticationFailed("Invalid or expired refresh token.") from exc
    _admin_from_token(token)  # ensures realm + still-active
    return str(token.access_token)


class AdminJWTAuthentication(BaseAuthentication):
    """Authenticate an ``AdminUser`` from a Bearer access token."""

    keyword = "Bearer"

    def authenticate(self, request: Request) -> tuple[AdminUser, AccessToken] | None:
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None  # no credentials -> anonymous; permission layer 401s
        if len(header) != 2:
            raise AuthenticationFailed("Malformed Authorization header.")
        try:
            token = AccessToken(header[1].decode())  # type: ignore[arg-type]  # str at runtime
        except TokenError as exc:
            raise AuthenticationFailed("Invalid or expired token.") from exc
        admin = _admin_from_token(token)
        return (admin, token)

    def authenticate_header(self, request: Request) -> str:
        return self.keyword
