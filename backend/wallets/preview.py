"""Render a card's pass payloads against a throwaway sample customer.

The admin Wallet Studio needs to answer "what does this card actually produce?"
before anything is saved and before any real customer holds it. Building against
a live ``CustomerCard`` would either be impossible (a brand-new card has none) or
misleading (it would show one person's balance), so this builds an **unsaved**
sample instance and renders the real builders against it.

Nothing here writes to the database. The sample is never saved, and
``wallets.shortcode.code_for`` returns its placeholder code for unsaved cards
rather than allocating a row.
"""

from __future__ import annotations

from typing import Any

from core.enums import CustomerCardStatus
from core.models import Card, CustomerCard

# The sample holder. A recognisably fake name keeps a screenshot of the preview
# from ever being mistaken for a real member's pass.
SAMPLE_NAME = "Sample Customer"
SAMPLE_PHONE = "+201000000000"


def sample_customer_card(card: Card, stamp_count: int | None = None) -> CustomerCard:
    """An unsaved ``CustomerCard`` for ``card`` — never persisted.

    Defaults to a little over half the goal so the preview shows both earned and
    remaining stamps; a full or empty card hides one of the two states and makes
    the strip look wrong.
    """
    goal = card.stamps_required or 0
    if stamp_count is None:
        stamp_count = (goal + 1) // 2 if goal else 0
    return CustomerCard(
        card=card,
        merchant=card.merchant,
        customer_name=SAMPLE_NAME,
        customer_phone=SAMPLE_PHONE,
        stamp_count=max(0, min(stamp_count, goal) if goal else max(0, stamp_count)),
        status=CustomerCardStatus.ACTIVE,
    )


def build_preview(card: Card, stamp_count: int | None = None) -> dict[str, Any]:
    """Every payload the card renders, for one sample balance.

    Returns the Apple ``pass.json`` and both halves of the Google pass, each
    already carrying its admin overlay — so what the studio shows is what the
    phone gets. Each builder is guarded independently: a broken Google overlay
    should still let the admin see (and fix) the Apple side.
    """
    from wallets.apple.passdata import build_pass_json
    from wallets.google.builders import build_loyalty_class, build_loyalty_object

    sample = sample_customer_card(card, stamp_count)

    out: dict[str, Any] = {
        "stamp_count": sample.stamp_count,
        "stamps_required": card.stamps_required,
        "errors": {},
    }
    for key, build in (
        ("apple", lambda: build_pass_json(sample)),
        ("google_class", lambda: build_loyalty_class(card)),
        ("google_object", lambda: build_loyalty_object(sample)),
    ):
        try:
            out[key] = build()
        except Exception as exc:  # surfaced in the studio, not raised at the admin
            out[key] = None
            out["errors"][key] = f"{type(exc).__name__}: {exc}"
    return out
