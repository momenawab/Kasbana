"""Enrollment token issuance + resolution (contract §3.3 ENROLL_TOKEN_BYTES).

A merchant generates a token per program (Card); the QR encodes
``/enroll/{token}``. Tokens are random, URL-safe, and optionally expiring
(``ENROLL_TOKEN_TTL_DAYS`` is ``None`` = never expires by default).
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.utils import timezone

from common.errors import TokenExpired
from core import constants
from core.models import Card, EnrollmentToken


def _generate_token() -> str:
    # token_urlsafe(16) -> ~22 chars; fits EnrollmentToken.token (char 32).
    return secrets.token_urlsafe(constants.ENROLL_TOKEN_BYTES)


def issue_enrollment_token(card: Card) -> EnrollmentToken:
    """Create a fresh active enrollment token for a program (Card)."""
    expires_at = None
    if constants.ENROLL_TOKEN_TTL_DAYS is not None:
        expires_at = timezone.now() + timedelta(days=constants.ENROLL_TOKEN_TTL_DAYS)

    return EnrollmentToken.objects.create(
        merchant=card.merchant,
        card=card,
        token=_generate_token(),
        expires_at=expires_at,
        is_active=True,
    )


def resolve_active_token(token: str) -> EnrollmentToken | None:
    """Return the active token row, or ``None`` if missing/inactive.

    Raises ``TokenExpired`` (410) if it exists but is past ``expires_at``.
    """
    row = (
        EnrollmentToken.objects.select_related("card", "merchant")
        .filter(token=token, is_active=True)
        .first()
    )
    if row is None:
        return None
    if row.expires_at is not None and row.expires_at < timezone.now():
        raise TokenExpired()
    return row
