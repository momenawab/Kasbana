"""Build Google Wallet LoyaltyClass / LoyaltyObject payloads (contract §3.4).

A LoyaltyClass is created once per Card (the program template); a LoyaltyObject
once per CustomerCard (the customer's instance). IDs are namespaced under the
issuer id and must be `[issuerId].[alphanumeric._-]`.
"""

from __future__ import annotations

from django.conf import settings

from core import constants
from core.models import Card, CustomerCard
from wallets.google.config import issuer_id


def class_id_for(card: Card) -> str:
    return f"{issuer_id()}.card_{card.id.hex}"


def object_id_for(customer_card: CustomerCard) -> str:
    return f"{issuer_id()}.cust_{customer_card.id.hex}"


def _hex_color(value: str, fallback: str) -> str:
    return value if value else fallback


def build_loyalty_class(card: Card) -> dict:
    from wallets import design as design_mod

    merchant = card.merchant
    design = design_mod.get_design(card)
    # Google requires a program logo on every class; fall back to the default.
    program_logo = card.logo_url or merchant.logo_url or settings.WALLET_DEFAULT_LOGO_URL
    payload: dict = {
        "id": class_id_for(card),
        "issuerName": merchant.name,
        "programName": (design.google_title if design and design.google_title else card.name),
        "reviewStatus": "UNDER_REVIEW",
        "hexBackgroundColor": _hex_color(card.color_bg or merchant.color_bg, "#0b7a5b"),
        "countryCode": "EG",
        "programLogo": {
            "sourceUri": {"uri": program_logo},
            "contentDescription": {
                "defaultValue": {"language": "en", "value": f"{merchant.name} logo"}
            },
        },
    }
    if card.reward_title:
        payload["rewardsTier"] = card.reward_title
    # Optional wide banner image shown across the top of the pass.
    if card.hero_image_url:
        payload["heroImage"] = {
            "sourceUri": {"uri": card.hero_image_url},
            "contentDescription": {
                "defaultValue": {"language": "en", "value": f"{card.name} banner"}
            },
        }
    return payload


def unit_label(card: Card) -> str:
    """ "Points" for a points card, else "Stamps" — the wallet balance label."""
    from core.enums import CardType

    return "Points" if card.type == CardType.POINTS else "Stamps"


def object_state_for(customer_card: CustomerCard) -> str:
    """Google LoyaltyObject ``state`` from the card status — EXPIRED moves the
    pass out of the wallet's active list (single-use completion / blocked)."""
    from core.enums import CustomerCardStatus

    return "ACTIVE" if customer_card.status == CustomerCardStatus.ACTIVE else "EXPIRED"


def build_loyalty_object(customer_card: CustomerCard) -> dict:
    from wallets import design as design_mod
    from wallets.shortcode import code_for

    card = customer_card.card
    barcode_value = f"{constants.PASS_BARCODE_PREFIX}{customer_card.id.hex}"
    payload: dict = {
        "id": object_id_for(customer_card),
        "classId": class_id_for(card),
        "state": object_state_for(customer_card),
        "accountId": str(customer_card.id),
        "accountName": customer_card.customer_name or customer_card.customer_phone,
        "loyaltyPoints": {
            "label": unit_label(card),
            "balance": {"int": customer_card.stamp_count},
        },
        "secondaryLoyaltyPoints": {
            "label": "Goal",
            "balance": {"int": card.stamps_required},
        },
        "barcode": {
            "type": "QR_CODE",
            "value": barcode_value,
            # Short human code under the QR — a cashier can type it on Scan (note 1).
            "alternateText": code_for(customer_card),
        },
    }

    # Merchant module rows + subtitle (notes 2-4). Google renders these as
    # textModulesData under the balance; blank/empty = none (unchanged default).
    design = design_mod.get_design(card)
    if design:
        modules: list[dict] = []
        if design.google_subtitle:
            modules.append({"id": "subtitle", "header": "", "body": design.google_subtitle})
        if design.google_rows:
            ctx = design_mod.field_context(customer_card)
            for slot in design_mod.render_slots(design.google_rows, ctx):
                modules.append(
                    {"id": slot["key"], "header": slot["label"], "body": str(slot["value"])}
                )
        if modules:
            payload["textModulesData"] = modules

    return payload
