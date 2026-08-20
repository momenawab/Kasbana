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
from wallets import overlay as overlay_mod
from wallets.design import VALUE_TOKENS

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


def token_context() -> dict[str, str]:
    """A value context that resolves every token to *itself*.

    Feeding this to the pass builders renders the pass's real structure with
    ``{balance}`` / ``{remaining}`` still in place instead of one customer's
    numbers. That is what makes the result safe to adopt as an overlay: a
    scaffold full of literal numbers would freeze every holder at the sample
    balance, which is the whole failure mode the token system exists to prevent.
    """
    return {token: "{" + token + "}" for token in VALUE_TOKENS}


def build_scaffold(card: Card) -> dict[str, Any]:
    """The card's current pass payloads in editable, token-preserving form.

    The Wallet Studio shows this when a card was built in the Editor and has no
    overlay yet, so an admin starts from the real pass rather than an empty
    document. Locked keys are stripped: they can never be part of an overlay, so
    including them would only produce a validation error the moment the admin
    copied it across.
    """
    from wallets.apple.passdata import build_pass_json
    from wallets.google.builders import build_loyalty_class, build_loyalty_object

    sample = sample_customer_card(card)
    ctx = token_context()

    out: dict[str, Any] = {"errors": {}}
    for key, build, locked in (
        ("apple", lambda: build_pass_json(sample, ctx), overlay_mod.LOCKED_APPLE),
        ("google_class", lambda: build_loyalty_class(card), overlay_mod.LOCKED_GOOGLE_CLASS),
        (
            "google_object",
            lambda: build_loyalty_object(sample, ctx),
            overlay_mod.LOCKED_GOOGLE_OBJECT,
        ),
    ):
        try:
            out[key] = overlay_mod.strip_locked(build(), locked)
        except Exception as exc:
            out[key] = None
            out["errors"][key] = f"{type(exc).__name__}: {exc}"
    return out


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
