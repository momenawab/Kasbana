"""Impersonation service (Phase 6) — mint + control view-as-merchant sessions.

The token is a real *merchant* access token (so the dashboard works unchanged)
for the merchant's owner identity, with two extra claims:

- ``impersonated_by``: the admin's id — attribution;
- ``impersonation_id``: the ``Impersonation`` row — lets the merchant auth layer
  (``common.auth.MerchantJWTAuthentication``) kill the session server-side when
  an admin ends it, before the JWT's own (short) expiry.

No refresh token is ever issued — the session hard-stops at ``expires_at``.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from console.models import AdminUser, Impersonation
from core.enums import Role
from core.models import Merchant, StaffUser

IMPERSONATION_MINUTES = 15
IMPERSONATED_BY_CLAIM = "impersonated_by"
IMPERSONATION_ID_CLAIM = "impersonation_id"


def impersonation_target(merchant: Merchant) -> StaffUser | None:
    """The staff identity to impersonate — the owner, else any active staff."""
    staff = (
        StaffUser.objects.filter(merchant=merchant, is_active=True)
        .select_related("user")
        .order_by("created_at")
    )
    return staff.filter(role=Role.OWNER).first() or staff.first()


def start_impersonation(
    admin: AdminUser, merchant: Merchant, target: StaffUser, reason: str
) -> tuple[Impersonation, str]:
    """Create the session row + mint its short-lived merchant access token."""
    now = timezone.now()
    imp = Impersonation.objects.create(
        admin=admin,
        admin_email=admin.email,
        merchant=merchant,
        target_email=target.user.email,
        reason=reason,
        expires_at=now + timedelta(minutes=IMPERSONATION_MINUTES),
    )
    token = AccessToken.for_user(target.user)
    token.set_exp(from_time=now, lifetime=timedelta(minutes=IMPERSONATION_MINUTES))
    token[IMPERSONATED_BY_CLAIM] = str(admin.id)
    token[IMPERSONATION_ID_CLAIM] = str(imp.id)
    return imp, str(token)


def end_impersonation(imp: Impersonation) -> Impersonation:
    """Mark the session ended (idempotent) — its token dies on the next request."""
    if imp.ended_at is None:
        imp.ended_at = timezone.now()
        imp.save(update_fields=["ended_at"])
    return imp
