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

import json
from typing import Any

from rest_framework import serializers

from wallets import overlay as overlay_mod
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


def _bounded_scale(value: Any, low: float, high: float, label: str) -> float:
    """A size multiplier inside sane bounds.

    Bounded rather than free because the failure is silent: too large and the
    stamps overlap into an unreadable smear, too small and they vanish against
    the strip — neither raises, both just ship a broken-looking pass.
    """
    try:
        scale = float(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError(f"{label} must be a number.") from None
    if not low <= scale <= high:
        raise serializers.ValidationError(f"{label} must be between {low} and {high}.")
    return scale


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
            "strip_bg_image_url",
            "strip_stamps_visible",
            "stamp_scale",
            "logo_scale",
        ]

    def validate_stamp_scale(self, value: Any) -> float:
        return _bounded_scale(value, 0.5, 1.6, "Stamp size")

    def validate_logo_scale(self, value: Any) -> float:
        # Capped at 1.0: Apple's logo slot is 160x50 pt and nothing renders past
        # it, so allowing 1.4 here would silently do nothing and read as a bug.
        return _bounded_scale(value, 0.4, 1.0, "Logo size")

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


def _validate_overlay(value: Any, locked: frozenset[str], label: str) -> dict[str, Any]:
    """Validate one admin-authored pass overlay.

    Rejects the locked identity keys **by name** rather than dropping them
    silently — an admin who thinks they set ``serialNumber`` and sees it vanish
    would keep trying. Also bounds size and nesting, because whatever is written
    here ends up inside every signed .pkpass for the card.
    """
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise serializers.ValidationError(f"{label} must be a JSON object.")

    violations = overlay_mod.locked_violations(value, locked)
    if violations:
        raise serializers.ValidationError(
            f"These keys are managed by the platform and cannot be set: "
            f"{', '.join(violations)}. They control pass identity, updates and "
            f"scanning — overriding them would break passes already in wallets."
        )

    if len(json.dumps(value)) > overlay_mod.MAX_OVERLAY_BYTES:
        raise serializers.ValidationError(
            f"{label} is too large (max {overlay_mod.MAX_OVERLAY_BYTES:,} bytes)."
        )
    if _depth(value) > overlay_mod.MAX_OVERLAY_DEPTH:
        raise serializers.ValidationError(f"{label} is nested too deeply.")
    return value


def _depth(value: Any, level: int = 1) -> int:
    """Deepest nesting level in a JSON value (guards pathological documents)."""
    if isinstance(value, dict):
        children = value.values()
    elif isinstance(value, list):
        children = value
    else:
        return level
    return max((_depth(v, level + 1) for v in children), default=level)


class AdminWalletCardDesignSerializer(WalletCardDesignSerializer):
    """The design serializer plus the admin-only raw pass JSON overlays.

    Two things separate it from the merchant serializer:

    * ``apple_overlay``/``google_overlay`` are writable. They are deliberately
      absent from the merchant serializer — a raw pass payload is a platform-admin
      tool, and exposing it on the dashboard endpoint would let any merchant author
      arbitrary pass content.
    * The template ``editable`` allowlist is not applied. An admin building a
      bespoke card is authoring *past* the template registry by definition, so
      locking them to a template's editable set would defeat the feature.
    """

    class Meta(WalletCardDesignSerializer.Meta):
        fields = [*WalletCardDesignSerializer.Meta.fields, "apple_overlay", "google_overlay"]

    def validate_apple_overlay(self, v: Any) -> dict[str, Any]:
        return _validate_overlay(v, overlay_mod.LOCKED_APPLE, "Apple overlay")

    def validate_google_overlay(self, v: Any) -> dict[str, Any]:
        if v in (None, ""):
            return {}
        if not isinstance(v, dict):
            raise serializers.ValidationError("Google overlay must be a JSON object.")
        unknown = sorted(set(v) - set(overlay_mod.GOOGLE_SECTIONS))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown section(s): {', '.join(unknown)}. A Google overlay has two "
                f'halves — {{"class": {{...}}, "object": {{...}}}} — because Google '
                f"splits one pass into a per-card class and a per-customer object."
            )
        return {
            section: _validate_overlay(
                v[section], overlay_mod.GOOGLE_SECTIONS[section], f"Google {section} overlay"
            )
            for section in v
        }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Skip the template allowlist — an admin authors past the templates."""
        return attrs
