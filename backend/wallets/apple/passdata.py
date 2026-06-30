"""Build the Apple Wallet pass.json for a CustomerCard (contract §3.4).

A storeCard-style loyalty pass. ``serialNumber`` is the CustomerCard id (= the
wallet serial, per the contract) and ``authenticationToken`` is the per-pass
secret used by the web service.
"""

from __future__ import annotations

from django.conf import settings

from core import constants
from core.models import CustomerCard
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


def build_pass_json(customer_card: CustomerCard) -> dict:
    card = customer_card.card
    merchant = card.merchant
    bg = _rgb(card.color_bg or merchant.color_bg, "#0b7a5b")
    fg = _rgb(card.color_fg or merchant.color_fg, "#ffffff")

    return {
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
        "logoText": merchant.name,
        "storeCard": {
            "primaryFields": [
                {"key": "stamps", "label": "Stamps", "value": customer_card.stamp_count}
            ],
            "secondaryFields": [{"key": "goal", "label": "Goal", "value": card.stamps_required}],
            "auxiliaryFields": (
                [{"key": "reward", "label": "Reward", "value": card.reward_title}]
                if card.reward_title
                else []
            ),
            "backFields": _message_back_fields(customer_card),
        },
        "barcodes": [
            {
                "format": "PKBarcodeFormatQR",
                "message": f"{constants.PASS_BARCODE_PREFIX}{customer_card.id.hex}",
                "messageEncoding": "iso-8859-1",
                "altText": customer_card.customer_phone,
            }
        ],
    }
