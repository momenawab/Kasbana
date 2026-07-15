"""Wallet card-design serializer (notes 2-4 + templates).

Validates the editable Apple/Google pass variables. Field slots are
``{"label": str, "source": str}`` where ``source`` is a value token
(``wallets.design.VALUE_TOKENS``) or ``"text:<literal>"``. Per-region caps mirror
what each platform actually renders so a merchant can't overflow the pass.

When a layout-locked **template** is active (``template_key`` set to a registry
key), only that template's ``editable`` variables may be written — freeform slot
fields and the strip/hero toggles are silently dropped (the template locks the
layout). ``template_key == "custom"`` keeps the freeform editor untouched.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from wallets import stamp_icons as stamp_icons_mod
from wallets import templates as templates_mod
from wallets.design import VALUE_TOKENS
from wallets.models import WalletCardDesign

# Max slots per region (Apple caps most field areas at ~4).
_REGION_CAPS = {
    "apple_header": 3,
    "apple_primary": 1,
    "apple_secondary": 4,
    "apple_auxiliary": 4,
    "apple_back": 6,
    "google_rows": 3,
}


def _validate_slots(value: Any, cap: int) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise serializers.ValidationError("Expected a list of fields.")
    if len(value) > cap:
        raise serializers.ValidationError(f"At most {cap} field(s) allowed here.")
    cleaned: list[dict[str, str]] = []
    for slot in value:
        if not isinstance(slot, dict):
            raise serializers.ValidationError("Each field must be an object.")
        source = str(slot.get("source", "")).strip()
        if not source:
            raise serializers.ValidationError("Each field needs a value source.")
        if source not in VALUE_TOKENS and not source.startswith("text:"):
            raise serializers.ValidationError(f"Unknown value source: {source!r}.")
        cleaned.append({"label": str(slot.get("label", "")).strip(), "source": source})
    return cleaned


class WalletCardDesignSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletCardDesign
        fields = [
            "label_color",
            "apple_logo_text",
            "apple_header",
            "apple_primary",
            "apple_secondary",
            "apple_auxiliary",
            "apple_back",
            "apple_strip_enabled",
            "strip_bg_color",
            "strip_empty_url",
            "strip_filled_url",
            "stamp_icon",
            "stamp_color",
            "stamp_layout",
            "google_title",
            "google_subtitle",
            "google_rows",
            "google_stamp_hero",
            "template_key",
            "bottom_image_url",
        ]

    def validate_stamp_icon(self, value: Any) -> str:
        key = str(value or "").strip()
        if key and not stamp_icons_mod.is_valid(key):
            raise serializers.ValidationError(f"Unknown stamp icon: {key!r}.")
        return key

    def validate_template_key(self, value: Any) -> str:
        key = str(value or templates_mod.CUSTOM).strip()
        if not templates_mod.is_template_key(key):
            raise serializers.ValidationError(f"Unknown template: {key!r}.")
        return key

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Drop fields the active template doesn't allow (layout is locked)."""
        key = attrs.get("template_key")
        if key is None and self.instance is not None:
            key = self.instance.template_key
        template = templates_mod.get_template(str(key or templates_mod.CUSTOM))
        if template is not None:
            allowed = set(template["editable"])
            for field in list(attrs.keys()):
                if field == "template_key":
                    continue
                if field not in allowed:
                    attrs.pop(field, None)
        return attrs

    def validate_apple_header(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["apple_header"])

    def validate_apple_primary(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["apple_primary"])

    def validate_apple_secondary(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["apple_secondary"])

    def validate_apple_auxiliary(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["apple_auxiliary"])

    def validate_apple_back(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["apple_back"])

    def validate_google_rows(self, v: Any) -> list[dict[str, str]]:
        return _validate_slots(v, _REGION_CAPS["google_rows"])
