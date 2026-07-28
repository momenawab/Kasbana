"""Test ("demo") cards — the sales pitch tool.

Builds a fully-working, branded wallet pass for a *prospect* who has not signed
up yet, so a rep can show them their own card in Apple/Google Wallet during a
proposal instead of asking the business to create one first.

Three objects are needed for a pass to exist, and this module creates all of
them in one call:

1. a **demo ``Merchant``** (``is_demo=True``) — the wallet pipeline reads the
   brand straight off the merchant (Apple ``organizationName`` / ``logoText``,
   Google ``issuerName``), so the prospect's name must live on a merchant row;
2. a **``Card``** — the program template (the same fields the merchant
   dashboard's Card Designer writes);
3. a **``CustomerCard``** — passes are issued per *enrolled customer*, never per
   card, so a demo holder is enrolled to make the pass real.

Demo merchants are excluded from every real console surface
(``console.merchants.real_merchants``) and never counted, billed or moderated.
Plan limits are deliberately not consulted: a demo must never fail because a
throwaway account looks over quota.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.services import unique_slug
from core import ledger
from core.enums import CardStatus
from core.models import Card, CustomerCard, EnrollmentToken, Merchant
from wallets import service as wallet

logger = logging.getLogger(__name__)

# The demo holder enrolled behind every test card. A recognisable name so the
# pass reads sensibly when the prospect looks at it on the rep's phone.
DEMO_HOLDER_NAME = "Demo Customer"


def _enrollment_token(card: Card) -> str:
    """A join link token for the demo card, so the pass can be re-added later."""
    token = secrets.token_urlsafe(12)[:32]
    EnrollmentToken.objects.create(merchant=card.merchant, card=card, token=token)
    return token


@transaction.atomic
def create_demo_card(*, merchant_name: str, card_fields: dict[str, Any]) -> dict[str, Any]:
    """Create a demo merchant + card + enrolled holder, and provision its passes.

    ``card_fields`` mirrors the merchant Card Designer's payload (type, name,
    stamps_required, reward_title/description, colours, images, single_use,
    referral_enabled). Returns the created ids plus the Apple/Google add-to-wallet
    URLs — either may be ``None`` when that platform's credentials are absent, in
    which case the caller shows the pass as unavailable rather than failing.
    """
    name = merchant_name.strip()

    # A fresh demo merchant per test card. Reusing one across prospects would
    # brand every pass with whichever name was typed first, since the pass reads
    # the merchant, not the card.
    merchant = Merchant.objects.create(
        name=name,
        slug=unique_slug(f"demo-{name}"),
        is_demo=True,
        logo_url=card_fields.get("logo_url", "") or "",
        color_bg=card_fields.get("color_bg", "") or "",
        color_fg=card_fields.get("color_fg", "") or "",
    )

    card = Card.objects.create(
        merchant=merchant,
        type=card_fields.get("type", "STAMP"),
        name=card_fields["name"],
        stamps_required=int(card_fields.get("stamps_required", 8)),
        reward_title=card_fields.get("reward_title", ""),
        reward_description=card_fields.get("reward_description", "") or "",
        color_bg=card_fields.get("color_bg", "") or "",
        color_fg=card_fields.get("color_fg", "") or "",
        logo_url=card_fields.get("logo_url", "") or "",
        hero_image_url=card_fields.get("hero_image_url", "") or "",
        single_use=bool(card_fields.get("single_use", False)),
        referral_enabled=bool(card_fields.get("referral_enabled", False)),
        # Published straight away — a draft card has no live pass to show.
        status=CardStatus.ACTIVE,
    )

    # The demo holder. No phone/email: this is not a real person, and leaving
    # them blank keeps the record out of any contactable audience.
    holder = CustomerCard.objects.create(
        card=card,
        merchant=merchant,
        customer_name=DEMO_HOLDER_NAME,
        stamp_count=int(card_fields.get("preview_stamps", 0) or 0),
        enrolled_at=timezone.now(),
    )

    token = _enrollment_token(card)

    # Provisioning reaches Apple/Google. A failure must not roll back the card the
    # rep just built — surface null URLs and let them retry from the detail view.
    apple_url = google_url = None
    try:
        result = wallet.provision(holder)
        apple_url, google_url = result.apple_pass_url, result.google_save_url
    except Exception:  # pragma: no cover - network/credential failure
        logger.exception("demo card pass provisioning failed (merchant=%s)", merchant.id)

    return {
        "merchant_id": merchant.id,
        "card_id": card.id,
        "customer_card_id": holder.id,
        "merchant_name": merchant.name,
        "card_name": card.name,
        "enroll_token": token,
        "apple_pass_url": apple_url,
        "google_save_url": google_url,
        "stamp_count": holder.stamp_count,
        "stamps_required": card.stamps_required,
        "created_at": card.created_at,
    }


def demo_card_rows() -> list[dict[str, Any]]:
    """Every demo card built so far, newest first — the console list view."""
    cards = (
        Card.objects.filter(merchant__is_demo=True)
        .select_related("merchant")
        .order_by("-created_at")
    )
    rows = []
    for card in cards:
        holder = card.customer_cards.order_by("created_at").first()
        token = card.enrollment_tokens.filter(is_active=True).first()
        rows.append(
            {
                "merchant_id": card.merchant_id,
                "card_id": card.id,
                "customer_card_id": holder.id if holder else None,
                "merchant_name": card.merchant.name,
                "card_name": card.name,
                "enroll_token": token.token if token else "",
                "stamp_count": holder.stamp_count if holder else 0,
                "stamps_required": card.stamps_required,
                "created_at": card.created_at,
            }
        )
    return rows


def pass_urls(card: Card) -> dict[str, str | None]:
    """Re-provision and return the add-to-wallet URLs for an existing demo card."""
    holder = card.customer_cards.order_by("created_at").first()
    if holder is None:
        return {"apple_pass_url": None, "google_save_url": None}
    result = wallet.provision(holder)
    return {
        "apple_pass_url": result.apple_pass_url,
        "google_save_url": result.google_save_url,
    }


def _holder(card: Card) -> CustomerCard | None:
    return card.customer_cards.order_by("created_at").first()


@transaction.atomic
def stamp_demo_card(card: Card, *, delta: int = 1) -> dict[str, Any]:
    """Add ``delta`` stamps to the demo card and push the pass update live.

    This is the moment that sells the product in a proposal — the rep taps
    "stamp" and the prospect watches their own wallet pass tick over. It runs the
    real ledger path (so the demo behaves exactly like production), but with the
    anti-fraud guards off: the 30-second cooldown and 12-per-day cap exist to
    protect real reward economics, and would otherwise stall the pitch. A demo
    card has nothing to defraud.
    """
    holder = _holder(card)
    if holder is None:
        return {"stamp_count": 0, "stamps_required": card.stamps_required, "reward_ready": False}

    ledger.add_stamp(holder, delta=delta, note="Demo stamp (console)", skip_guards=True)
    holder.refresh_from_db(fields=["stamp_count", "last_event_at"])

    # Best-effort: the pass refreshes on its next device pull even if the push
    # fails, and a failed push must not read as a failed stamp.
    try:
        wallet.push_update(holder)
    except Exception:  # pragma: no cover - broker/credentials unavailable
        logger.exception("demo card pass push failed (card=%s)", card.id)

    return {
        "stamp_count": holder.stamp_count,
        "stamps_required": card.stamps_required,
        "reward_ready": holder.stamp_count >= card.stamps_required,
    }


@transaction.atomic
def reset_demo_card(card: Card) -> dict[str, Any]:
    """Zero the demo card's stamps so the same pass can be pitched again."""
    holder = _holder(card)
    if holder is None:
        return {"stamp_count": 0, "stamps_required": card.stamps_required, "reward_ready": False}

    holder.stamp_count = 0
    holder.save(update_fields=["stamp_count", "updated_at"])
    try:
        wallet.push_update(holder)
    except Exception:  # pragma: no cover - broker/credentials unavailable
        logger.exception("demo card pass push failed (card=%s)", card.id)

    return {
        "stamp_count": 0,
        "stamps_required": card.stamps_required,
        "reward_ready": False,
    }


@transaction.atomic
def delete_demo_card(card: Card) -> None:
    """Delete a demo card and the throwaway merchant created with it."""
    merchant = card.merchant
    card.delete()
    # The demo merchant exists only for this card; drop it too so the tool does
    # not accumulate orphan brands. Guarded in case one ever gets reused.
    if merchant.is_demo and not merchant.cards.exists():
        merchant.delete()
