"""Merchant contact + social links shown on the wallet pass back.

Single source of truth for both wallet builders: ``wallets/apple/passdata.py``
renders these as ``backFields`` (with clickable ``attributedValue`` links), and
``wallets/google/builders.py`` renders them as ``linksModuleData`` /
``textModulesData``. Each entry is optional — only the ones the merchant filled
in on the Settings screen appear. "Powered by Stampn" is always appended last.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Merchant

STAMPN_URL = "https://stampn.net"
STAMPN_LABEL = "Stampn"


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def contact_entries(merchant: Merchant) -> list[dict]:
    """Populated contact/social entries for ``merchant``, in display order.

    Each entry: ``{key, label, value, url}``. ``url`` set = a hyperlink; ``url``
    ``None`` = plain text (phone auto-links as tel in the wallet; branches is text).
    """
    from accounts.models import MerchantSettings

    s = MerchantSettings.objects.filter(merchant=merchant).first()
    if s is None:
        return []

    out: list[dict] = []

    def add(key: str, label: str, value: str, url: str | None) -> None:
        v = (value or "").strip()
        if v:
            out.append({"key": key, "label": label, "value": v, "url": url})

    add("phone", "Phone", s.contact_phone, None)
    add("branches", "Branches", s.branches, None)
    add("facebook", "Facebook", s.facebook_url, (s.facebook_url or "").strip() or None)
    add("instagram", "Instagram", s.instagram_url, (s.instagram_url or "").strip() or None)

    wa = (s.whatsapp or "").strip()
    if wa:
        wa_url = wa if wa.startswith("http") else f"https://wa.me/{_digits(wa)}"
        out.append({"key": "whatsapp", "label": "WhatsApp", "value": wa_url, "url": wa_url})

    add("tiktok", "TikTok", s.tiktok_url, (s.tiktok_url or "").strip() or None)
    add("terms", "Terms & Conditions", s.terms_url, (s.terms_url or "").strip() or None)
    return out


def apple_back_fields(merchant: Merchant) -> list[dict]:
    """Contact/social ``backFields`` for the Apple pass (excludes Powered by)."""
    fields: list[dict] = []
    for e in contact_entries(merchant):
        if e["url"]:
            # attributedValue lets the label itself be the tappable link.
            fields.append(
                {
                    "key": e["key"],
                    "label": e["label"],
                    "value": e["url"],
                    "attributedValue": f'<a href="{escape(e["url"], quote=True)}">'
                    f"{escape(e['label'])}</a>",
                }
            )
        else:
            # Phone auto-links (tel); branches renders as plain multi-line text.
            fields.append({"key": e["key"], "label": e["label"], "value": e["value"]})
    return fields


def apple_powered_by() -> dict:
    """The always-last "Powered by Stampn" backField, with Stampn hyperlinked."""
    return {
        "key": "powered",
        "label": "",
        "value": f"Powered by {STAMPN_LABEL}",
        "attributedValue": f'Powered by <a href="{STAMPN_URL}">{STAMPN_LABEL}</a>',
    }


def google_links(merchant: Merchant) -> list[dict]:
    """``linksModuleData.uris`` entries (hyperlinks + phone tel), Powered by last."""
    uris: list[dict] = []
    for e in contact_entries(merchant):
        if e["url"]:
            uris.append({"id": e["key"], "uri": e["url"], "description": e["label"]})
        elif e["key"] == "phone":
            uris.append(
                {"id": "phone", "uri": f"tel:{_digits(e['value'])}", "description": "Phone"}
            )
    uris.append(
        {"id": "powered", "uri": STAMPN_URL, "description": f"Powered by {STAMPN_LABEL}"}
    )
    return uris


def google_branch_text(merchant: Merchant) -> str:
    """Branches free text, if set (Google has no link slot for multi-line text)."""
    for e in contact_entries(merchant):
        if e["key"] == "branches":
            return e["value"]
    return ""
