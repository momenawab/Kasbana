"""Wallet card design resolution + value-token rendering (notes 2-4).

The pass builders (``wallets.apple.passdata`` / ``wallets.google.builders``)
compute a smart default layout from the card. A merchant can override any region
via a :class:`wallets.models.WalletCardDesign` row; the builders call in here to
turn a stored field slot into a rendered ``{label, value}`` for a given customer.

A slot is ``{"label": str, "source": str}`` where ``source`` is one of
:data:`VALUE_TOKENS` or ``"text:<literal>"`` for static text. Blank/empty design
lists mean "keep the built-in default", so a card without a design row is
unchanged.
"""

from __future__ import annotations

from typing import Any

from core.enums import CardType
from core.models import Card, CustomerCard

# Dynamic value tokens a field slot can reference. Keep in sync with the editor.
VALUE_TOKENS = {
    "balance",  # "count/goal" (or count when no goal)
    "stamps",  # earned count
    "points",  # earned count (points cards)
    "goal",  # stamps_required
    "remaining",  # goal - count (never below 0)
    "reward",  # card.reward_title
    "merchant",  # merchant name
    "program",  # card name
}


def get_design(card: Card) -> Any | None:
    """Return the card's ``WalletCardDesign`` row, or ``None`` if unset."""
    try:
        return card.wallet_design
    except Exception:  # OneToOne with no row → RelatedObjectDoesNotExist
        return None


def unit_label(card: Card) -> str:
    return "Points" if card.type == CardType.POINTS else "Stamps"


def field_context(customer_card: CustomerCard) -> dict[str, Any]:
    """Values the tokens resolve against for one customer's pass."""
    card = customer_card.card
    count = customer_card.stamp_count
    goal = card.stamps_required
    return {
        "balance": f"{count}/{goal}" if goal else count,
        "stamps": count,
        "points": count,
        "goal": goal,
        "remaining": max(0, goal - count) if goal else 0,
        "reward": card.reward_title,
        "merchant": card.merchant.name,
        "program": card.name,
    }


def render_value(source: str, ctx: dict[str, Any]) -> Any:
    """Resolve a slot ``source`` to a display value.

    ``text:<literal>`` returns the literal; a known token returns its value; an
    unknown source falls back to the raw string so a typo shows rather than 500s.
    """
    if source.startswith("text:"):
        return source[len("text:") :]
    if source in ctx:
        return ctx[source]
    return source


def render_slots(
    slots: list[dict[str, Any]], ctx: dict[str, Any], prefix: str = "f"
) -> list[dict[str, Any]]:
    """Turn stored slots into pass field dicts (``key``/``label``/``value``).

    ``prefix`` namespaces the generated ``key`` per region — Apple requires every
    field ``key`` to be unique across the *whole* pass, so header/primary/
    secondary/... must not all start at ``f0`` (a collision makes iOS reject the
    pass: "Safari cannot download this file"). Skips malformed slots defensively
    so one bad row can't break the whole pass.
    """
    out: list[dict[str, Any]] = []
    for i, slot in enumerate(slots or []):
        if not isinstance(slot, dict):
            continue
        source = str(slot.get("source", "")).strip()
        if not source:
            continue
        out.append(
            {
                "key": f"{prefix}{i}",
                "label": str(slot.get("label", "")),
                "value": render_value(source, ctx),
            }
        )
    return out
