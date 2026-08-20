"""Enrollment token issuance + resolution (contract §3.3 ENROLL_TOKEN_BYTES).

Two kinds of token, both encoded as ``/enroll/{token}`` behind one public route:

* **Card token** (``core.EnrollmentToken``) — bound to one program forever.
* **Merchant token** (``enrollment.MerchantEnrollLink``) — the "main QR": stable
  across a change of program, so a printed poster never goes stale.

``resolve_join_target`` is the single entry point; it tries a card token first,
then the merchant link. Tokens are random, URL-safe, and optionally expiring
(``ENROLL_TOKEN_TTL_DAYS`` is ``None`` = never expires by default).
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from common.errors import TokenExpired
from core import constants
from core.enums import CardStatus
from core.models import Card, EnrollmentToken, Merchant
from enrollment.models import MerchantEnrollLink


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


def get_or_issue_enrollment_token(card: Card) -> EnrollmentToken:
    """Return the card's current active token, issuing one only if none exists.

    Read paths (e.g. the dashboard QR endpoint) must use this — calling
    ``issue_enrollment_token`` on every GET would change the join URL each view
    (breaking already-printed posters) and leak a token row per request.
    """
    existing = (
        EnrollmentToken.objects.filter(card=card, is_active=True).order_by("-created_at").first()
    )
    if existing is not None and (
        existing.expires_at is None or existing.expires_at > timezone.now()
    ):
        return existing
    return issue_enrollment_token(card)


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


def get_or_issue_merchant_link(merchant: Merchant) -> MerchantEnrollLink:
    """Return the merchant's main-QR link, creating it on first use.

    Idempotent under a concurrent double-GET: ``merchant`` is a OneToOne, so the
    loser of the race hits the unique constraint and re-reads the winner's row
    rather than minting a second token (which would silently orphan the first).
    """
    existing = MerchantEnrollLink.objects.filter(merchant=merchant).first()
    if existing is not None:
        return existing
    try:
        with transaction.atomic():
            return MerchantEnrollLink.objects.create(merchant=merchant, token=_generate_token())
    except IntegrityError:
        return MerchantEnrollLink.objects.get(merchant=merchant)


def rotate_merchant_link(merchant: Merchant) -> MerchantEnrollLink:
    """Mint a fresh token for the main QR, invalidating every printed poster."""
    link = get_or_issue_merchant_link(merchant)
    link.token = _generate_token()
    link.save(update_fields=["token", "updated_at"])
    return link


def resolve_join_target(token: str) -> tuple[Merchant, Card] | None:
    """Resolve a public join token to ``(merchant, card)``, or ``None`` (→ 404).

    A card token resolves to its own card (raising ``TokenExpired`` → 410 when
    past its TTL). A merchant token resolves to the elected ``primary_card``, but
    only when one is elected **and** it is ACTIVE — a DRAFT or ARCHIVED program
    must never take joins through the main QR, and an unset primary must 404
    rather than fall back to an arbitrary card.
    """
    card_token = resolve_active_token(token)
    if card_token is not None:
        return card_token.merchant, card_token.card

    link = (
        MerchantEnrollLink.objects.select_related("primary_card", "merchant")
        .filter(token=token, is_active=True)
        .first()
    )
    if link is None or link.primary_card is None:
        return None
    if link.primary_card.status != CardStatus.ACTIVE:
        return None
    return link.merchant, link.primary_card
