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


def build_pass_json(customer_card: CustomerCard, ctx: dict | None = None) -> dict:
    """The pass.json for one customer.

    ``ctx`` overrides the value context field slots resolve against. Real passes
    always leave it ``None`` (this customer's balance). The Wallet Studio passes
    a self-referencing token context so it can render the *shape* of the pass
    with ``{balance}`` still in place — see ``wallets.preview.build_scaffold``.
    """
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
    if ctx is None:
        ctx = design_mod.field_context(customer_card)
    label_color = _rgb(design.label_color, "#ffffff") if (design and design.label_color) else fg
    # A layout-locked template overrides the freeform regions entirely (its
    # positions are fixed) and pins the strip behaviour to its bottom_visual.
    template = design_mod.template_for(card)
    if template is not None:
        bottom_visual = template.get("bottom_visual", "none")
        use_strip = bottom_visual in ("stamps", "image")
        apple = template.get("apple", {})
        header_fields = design_mod.render_template_fields(apple.get("header", []), ctx, "h")
        primary_fields = design_mod.render_template_fields(apple.get("primary", []), ctx, "p")
        secondary_fields = design_mod.render_template_fields(apple.get("secondary", []), ctx, "s")
        auxiliary_fields = design_mod.render_template_fields(apple.get("auxiliary", []), ctx, "x")
    else:
        # The strip carries the stamp grid; when it's off, lead with the balance
        # in the primary area instead of leaving it clear for the strip.
        use_strip = is_stamp and (design.apple_strip_enabled if design else True)

        # Top-right header: compact progress next to the logo.
        header_fields = [
            {"key": "balance", "label": unit.upper(), "value": f"{count}/{goal}" if goal else count}
        ]

        # STAMP cards carry a strip image with the stamp grid, so keep the primary
        # (over-strip) area clear and show progress below in secondary fields — the
        # coffee-card layout. POINTS cards have no strip, so lead with the balance.
        if use_strip:
            primary_fields = []
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

        # Apply per-region overrides where the merchant configured slots. Each
        # region gets a distinct key prefix so field keys stay unique across the
        # whole pass (Apple rejects a pass with duplicate field keys — "Safari
        # cannot download").
        if design:
            if design.apple_header:
                header_fields = design_mod.render_slots(design.apple_header, ctx, "h")
            if design.apple_primary:
                primary_fields = design_mod.render_slots(design.apple_primary, ctx, "p")
            if design.apple_secondary:
                secondary_fields = design_mod.render_slots(design.apple_secondary, ctx, "s")
            if design.apple_auxiliary:
                auxiliary_fields = design_mod.render_slots(design.apple_auxiliary, ctx, "x")

    # Top-row branding: the merchant's brand owns the left (logo image + business
    # name in logoText), and the platform attribution owns the only top-right slot
    # Apple's storeCard offers — a header field. This "Stampn" header replaces the
    # numeric balance that templates put in the header: the strip's cup grid and
    # the "N for a reward" secondary field already convey progress, so the count is
    # redundant up top. Falls back to the template header only if no label is set.
    platform_label = str(getattr(settings, "WALLET_PLATFORM_LABEL", "") or "").strip()
    if platform_label:
        header_fields = [{"key": "brand", "value": platform_label}]

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

    # Merchant contact + social links (phone, branches, Facebook/Instagram/
    # WhatsApp/TikTok, Terms) — each only when the merchant filled it in — then
    # "Powered by Stampn" always dead last with Stampn hyperlinked.
    from wallets import contact as contact_mod

    back_fields.extend(contact_mod.apple_back_fields(merchant))
    back_fields.append(contact_mod.apple_powered_by())

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
    # logoText renders immediately to the right of the top-left logo image, so it
    # carries the merchant's *business name* — the brand the customer recognises.
    # A branded merchant may override the exact wording (design.apple_logo_text);
    # otherwise use the merchant name. Platform attribution ("Stampn") lives in the
    # top-right header field instead (see header_fields above), keeping the whole
    # left side the merchant's own brand: "[BrandLogo] Momen ...... Stampn".
    if design and design.apple_logo_text:
        payload["logoText"] = design.apple_logo_text
    elif merchant.name:
        payload["logoText"] = merchant.name
    # Custom strip artwork needs Apple's default gloss gradient turned off, or the
    # shine washes the photo out. Only set when there *is* artwork, so a plain
    # color strip keeps the stock PassKit look.
    if design and design.strip_bg_image_url:
        payload["suppressStripShine"] = True
    # Void a no-longer-active pass (single-use completion / blocked) — iOS greys
    # it out and marks it expired.
    if customer_card.status != CustomerCardStatus.ACTIVE:
        payload["voided"] = True

    # Admin-authored overlay, merged last so it wins over every generated default
    # — except the locked identity keys, which ``overlay`` strips. See
    # ``wallets.overlay`` for why serialNumber/authenticationToken/webServiceURL/
    # barcodes can never be overridden.
    from wallets import overlay as overlay_mod

    return overlay_mod.apply(
        payload,
        design.apple_overlay if design else None,
        ctx,
        overlay_mod.LOCKED_APPLE,
    )
