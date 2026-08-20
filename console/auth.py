"""Admin JWT auth — a boundary fully separate from the merchant auth.

Admin tokens carry a custom ``realm:"admin"`` claim + ``admin_id`` and NO
``user_id``. So:
- a merchant token hitting an admin endpoint fails (no ``realm:"admin"``);
- an admin token hitting a merchant endpoint fails (the default SimpleJWT auth
  looks up ``user_id``, which admin tokens lack).

Phase 15 adds sessions + MFA:
- full tokens carry a ``sid`` (``AdminSession`` id); every request checks the
  session is still active, so revoking it ("log out everywhere") kills the token
  immediately. Refresh tokens also carry ``re`` (the session's rotation epoch)
  for rotation + stolen-refresh reuse detection.
- half-authenticated states use a short **scoped** token (``scope`` =
  ``mfa_setup``/``mfa_challenge``). ``AdminJWTAuthentication`` rejects any scoped
  token, so a pending session can only reach the MFA-verify endpoint; the verify
  view uses ``resolve_pending`` to accept it.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from console.models import AdminSession, AdminUser

REALM_CLAIM = "realm"
ADMIN_REALM = "admin"
SCOPE_CLAIM = "scope"
SCOPE_MFA_SETUP = "mfa_setup"  # correct password, must still enrol MFA
SCOPE_MFA_CHALLENGE = "mfa_challenge"  # correct password, must still enter a code
PENDING_SCOPES = (SCOPE_MFA_SETUP, SCOPE_MFA_CHALLENGE)
PENDING_TOKEN_MINUTES = 10  # a half-auth token is short-lived


# ── token minting ────────────────────────────────────────────────────────────
def issue_admin_tokens(admin: AdminUser, session: AdminSession | None = None) -> dict[str, str]:
    """Mint a full ``{access, refresh}`` pair bound to a session.

    Custom claims set on the refresh token are copied onto its access token by
    SimpleJWT, so both carry ``realm`` + ``admin_id`` + ``sid``. When ``session``
    is omitted a bare session is created — every full token must be session-bound
    (the auth layer checks the session on each request), so there is no such thing
    as a session-less admin token.
    """
    if session is None:
        # The session-less convenience path (tests / internal mint) represents an
        # already-authenticated admin, so stamp it freshly authed. Production
        # always passes an explicit login/refresh session, never this branch.
        now = timezone.now()
        session = AdminSession.objects.create(admin=admin, last_auth_at=now, last_seen_at=now)
    refresh = RefreshToken()
    refresh[REALM_CLAIM] = ADMIN_REALM
    refresh["admin_id"] = str(admin.id)
    refresh["role"] = admin.role
    refresh["sid"] = str(session.id)
    refresh["re"] = session.refresh_epoch
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def issue_pending_token(admin: AdminUser, scope: str) -> str:
    """A short, scoped access token that ONLY the MFA-verify endpoint accepts."""
    token = AccessToken()
    token[REALM_CLAIM] = ADMIN_REALM
    token["admin_id"] = str(admin.id)
    token[SCOPE_CLAIM] = scope
    token.set_exp(lifetime=timedelta(minutes=PENDING_TOKEN_MINUTES))
    return str(token)


# ── shared resolution ────────────────────────────────────────────────────────
def _admin_by_id(admin_id: str | None) -> AdminUser:
    admin = AdminUser.objects.filter(id=str(admin_id or ""), is_active=True).first()
    if admin is None:
        raise AuthenticationFailed("Admin account not found or inactive.")
    return admin


def _full_admin_and_session(token: AccessToken | RefreshToken) -> tuple[AdminUser, AdminSession]:
    """Resolve a FULL admin token: realm ok, not scoped, active admin + session."""
    if token.get(REALM_CLAIM) != ADMIN_REALM:
        raise AuthenticationFailed("Not an admin token.")
    if token.get(SCOPE_CLAIM) in PENDING_SCOPES:
        # A half-auth (MFA-pending) token can never authenticate a real endpoint.
        raise AuthenticationFailed("Multi-factor authentication not completed.")
    admin = _admin_by_id(token.get("admin_id"))
    sid = token.get("sid")
    if not sid:
        # Pre-Phase-15 tokens carry no session — force a fresh sign-in once.
        raise AuthenticationFailed("Session expired, please sign in again.")
    session = AdminSession.objects.filter(id=sid, admin=admin, revoked=False).first()
    if session is None:
        raise AuthenticationFailed("Session ended, please sign in again.")
    return admin, session


def resolve_pending(raw_token: str) -> tuple[AdminUser, str]:
    """Validate a pending (MFA) token → ``(admin, scope)``."""
    try:
        token = AccessToken(raw_token)  # type: ignore[arg-type]  # str at runtime
    except TokenError as exc:
        raise AuthenticationFailed("Invalid or expired token.") from exc
    if token.get(REALM_CLAIM) != ADMIN_REALM or token.get(SCOPE_CLAIM) not in PENDING_SCOPES:
        raise AuthenticationFailed("Not a pending MFA token.")
    admin = _admin_by_id(token.get("admin_id"))
    return admin, token[SCOPE_CLAIM]


def refresh_admin_access(raw_refresh: str) -> dict[str, str]:
    """Rotate a refresh token: validate, detect reuse, issue a fresh pair.

    Each refresh bumps the session's ``refresh_epoch``. A refresh whose ``re``
    doesn't match the session is a replay of an already-rotated (likely stolen)
    token — we revoke the whole session and reject.
    """
    try:
        token = RefreshToken(raw_refresh)  # type: ignore[arg-type]  # str at runtime
    except TokenError as exc:
        raise AuthenticationFailed("Invalid or expired refresh token.") from exc
    admin, session = _full_admin_and_session(token)

    if token.get("re") != session.refresh_epoch:
        # Reuse of a rotated refresh token → treat the session as compromised.
        session.revoked = True
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked", "revoked_at"])
        raise AuthenticationFailed("Refresh token reuse detected; session revoked.")

    session.refresh_epoch += 1
    session.last_seen_at = timezone.now()
    session.save(update_fields=["refresh_epoch", "last_seen_at"])
    return issue_admin_tokens(admin, session)


# ── authenticators ───────────────────────────────────────────────────────────
class AdminJWTAuthentication(BaseAuthentication):
    """Authenticate an ``AdminUser`` from a full Bearer access token (+ session)."""

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
        admin, _session = _full_admin_and_session(token)
        return (admin, token)

    def authenticate_header(self, request: Request) -> str:
        return self.keyword
