"""Wallet card-design serializer (notes 2-4).

Validates the editable Apple/Google pass variables. Field slots are
``{"label": str, "source": str}`` where ``source`` is a value token
(``wallets.design.VALUE_TOKENS``) or ``"text:<literal>"``. Per-region caps mirror
what each platform actually renders so a merchant can't overflow the pass.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

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
            "strip_empty_url",
            "strip_filled_url",
            "google_title",
            "google_subtitle",
            "google_rows",
        ]

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
