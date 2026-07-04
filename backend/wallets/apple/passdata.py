"""Build the Apple Wallet pass.json for a CustomerCard (contract §3.4).

A storeCard-style loyalty pass. ``serialNumber`` is the CustomerCard id (= the
wallet serial, per the contract) and ``authenticationToken`` is the per-pass
secret used by the web service.
"""

from __future__ import annotations

from django.conf import settings

from core import constants
from core.models import Card, CustomerCard
from wallets.apple.config import pass_type_id, team_id


def _rgb(hex_color: str, fallback: str) -> str:
    h = (hex_color or fallback).lstrip("#")
    if len(h) != 6:
        h = fallback.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgb({r}, {g}, {b})"


def web_service_url() -> str:
    # Apple appends /v1/devices/... — must match the contract's path prefix.
    base = str(settings.BASE_URL or "").rstrip("/")
    return f"{base}/api/v1/wallet/apple"


def _message_back_fields(customer_card: CustomerCard) -> list[dict]:
    """A back field carrying the latest wallet message, if any.

    ``changeMessage`` "%@" is what makes iOS show a lock-screen notification with
    the new value when the pass is re-pulled after an APNs ping. Note Apple only
    notifies when the field value actually *differs* from the previous pull, so
    sending the identical text twice won't re-notify (distinct text always does).
    """
    from wallets.models import WalletMessage

    msg = WalletMessage.objects.filter(
        customer_card=customer_card
    ).first()  # newest (Meta.ordering)
    if msg is None:
        return []
    return [
        {
            "key": "message",
            "label": msg.title or "Message",
            "value": msg.body,
            "changeMessage": "%@",
        }
    ]


def _unit_label(card: Card) -> str:
    from core.enums import CardType

    return "Points" if card.type == CardType.POINTS else "Stamps"


def build_pass_json(customer_card: CustomerCard) -> dict:
    from core.enums import CardType, CustomerCardStatus
    from wallets import design as design_mod

    card = customer_card.card
    merchant = card.merchant
    unit = _unit_label(card)
    bg = _rgb(card.color_bg or merchant.color_bg, "#0b7a5b")
    fg = _rgb(card.color_fg or merchant.color_fg, "#ffffff")
    is_stamp = card.type == CardType.STAMP
    count = customer_card.stamp_count
    goal = card.stamps_required
    remaining = max(0, goal - count) if goal else 0

    # Merchant overrides (notes 2-4): any blank/empty slot keeps the smart default.
    design = design_mod.get_design(card)
    ctx = design_mod.field_context(customer_card)
    label_color = _rgb(design.label_color, "#ffffff") if (design and design.label_color) else fg
    # The strip carries the stamp grid; when it's off, lead with the balance in
    # the primary area instead of leaving it clear for the strip.
    use_strip = is_stamp and (design.apple_strip_enabled if design else True)

    # Top-right header: compact progress next to the logo.
    header_fields = [
        {"key": "balance", "label": unit.upper(), "value": f"{count}/{goal}" if goal else count}
    ]

    # STAMP cards carry a strip image with the stamp grid, so keep the primary
    # (over-strip) area clear and show progress below in secondary fields — the
    # coffee-card layout. POINTS cards have no strip, so lead with the balance.
    if use_strip:
        primary_fields: list[dict] = []
        secondary_fields = [
            {
                "key": "remaining",
                "label": "STAMPS UNTIL NEXT REWARD" if remaining else "REWARD READY 🎉",
                "value": remaining,
                "changeMessage": "%@ stamps until your next reward",
            }
        ]
    else:
        primary_fields = [{"key": "stamps", "label": unit, "value": count}]
        secondary_fields = [{"key": "goal", "label": "Goal", "value": goal}]

    auxiliary_fields = (
        [{"key": "reward", "label": "REWARD", "value": card.reward_title}]
        if card.reward_title
        else []
    )

    # Apply per-region overrides where the merchant configured slots. Each region
    # gets a distinct key prefix so field keys stay unique across the whole pass
    # (Apple rejects a pass with duplicate field keys — "Safari cannot download").
    if design:
        if design.apple_header:
            header_fields = design_mod.render_slots(design.apple_header, ctx, "h")
        if design.apple_primary:
            primary_fields = design_mod.render_slots(design.apple_primary, ctx, "p")
        if design.apple_secondary:
            secondary_fields = design_mod.render_slots(design.apple_secondary, ctx, "s")
        if design.apple_auxiliary:
            auxiliary_fields = design_mod.render_slots(design.apple_auxiliary, ctx, "x")

    back_fields: list[dict] = []
    if card.reward_title:
        back_fields.append(
            {"key": "reward_back", "label": "Your reward", "value": card.reward_title}
        )
    if card.reward_description:
        back_fields.append(
            {"key": "reward_desc", "label": "Details", "value": card.reward_description}
        )
    back_fields.append(
        {
            "key": "howto",
            "label": "How it works",
            "value": (
                f"Collect {goal} {unit.lower()} to earn your reward. "
                "Show this pass at checkout to get stamped."
                if is_stamp
                else "Earn points on every visit. Show this pass at checkout."
            ),
        }
    )
    back_fields.extend(_message_back_fields(customer_card))
    back_fields.append({"key": "merchant", "label": "Merchant", "value": merchant.name})
    if design and design.apple_back:
        back_fields.extend(design_mod.render_slots(design.apple_back, ctx, "b"))

    from wallets.shortcode import code_for

    barcode_message = f"{constants.PASS_BARCODE_PREFIX}{customer_card.id.hex}"
    barcode = {
        "format": "PKBarcodeFormatQR",
        "message": barcode_message,
        "messageEncoding": "iso-8859-1",
        # Short human code under the QR — a cashier can type it on Scan (note 1).
        "altText": code_for(customer_card),
    }

    payload = {
        "formatVersion": 1,
        "passTypeIdentifier": pass_type_id(),
        "serialNumber": str(customer_card.id),
        "teamIdentifier": team_id(),
        "organizationName": merchant.name,
        "description": card.name,
        "webServiceURL": web_service_url(),
        "authenticationToken": customer_card.auth_token,
        "backgroundColor": bg,
        "foregroundColor": fg,
        "labelColor": label_color,
        "sharingProhibited": True,
        "storeCard": {
            "headerFields": header_fields,
            "primaryFields": primary_fields,
            "secondaryFields": secondary_fields,
            "auxiliaryFields": auxiliary_fields,
            "backFields": back_fields,
        },
        # Modern (iOS 9+) array + legacy singular for older clients.
        "barcodes": [barcode],
        "barcode": barcode,
    }
    # logoText appears beside the logo image. A merchant override always wins;
    # otherwise omit it when a branded logo is set (the wordmark already carries
    # the name) to avoid a duplicate label.
    if design and design.apple_logo_text:
        payload["logoText"] = design.apple_logo_text
    elif not (card.logo_url or merchant.logo_url):
        payload["logoText"] = merchant.name
    # Void a no-longer-active pass (single-use completion / blocked) — iOS greys
    # it out and marks it expired.
    if customer_card.status != CustomerCardStatus.ACTIVE:
        payload["voided"] = True
    return payload
