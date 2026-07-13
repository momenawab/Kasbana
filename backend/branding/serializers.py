"""Registration-theme serializers (Phase 1 · finalize-phases · snake_case)."""

from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

from branding.defaults import FIELD_KEYS, QR_FRAMES, QR_MODULE_STYLES
from branding.models import RegistrationTheme

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{6})$")


class RegistrationThemeSerializer(serializers.ModelSerializer):
    """GET/PATCH body for the merchant's (or a card's) enroll theme."""

    class Meta:
        model = RegistrationTheme
        fields = [
            "template_key",
            "cover_image_url",
            "bg_color",
            "accent_color",
            "button_text_color",
            "font",
            "welcome_body",
            "fields_config",
            "qr_style",
            "terms_url",
            "privacy_url",
        ]

    def validate_fields_config(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object.")
        cleaned: dict[str, Any] = {}
        for key, cfg in value.items():
            if key not in FIELD_KEYS:
                raise serializers.ValidationError(f"Unknown field: {key!r}.")
            if not isinstance(cfg, dict):
                raise serializers.ValidationError(f"{key!r} must be an object.")
            cleaned[key] = {
                "show": bool(cfg.get("show", False)),
                "required": bool(cfg.get("required", False)),
            }
        return cleaned

    def validate_qr_style(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object.")
        module_style = value.get("module_style", "square")
        if module_style not in QR_MODULE_STYLES:
            raise serializers.ValidationError(f"module_style must be one of {QR_MODULE_STYLES}.")
        frame = value.get("frame", "none")
        if frame not in QR_FRAMES:
            raise serializers.ValidationError(f"frame must be one of {QR_FRAMES}.")
        cleaned: dict[str, Any] = {"module_style": module_style, "frame": frame}
        for color_key in ("fg_color", "bg_color"):
            color = value.get(color_key)
            if color:
                if not _HEX.match(color):
                    raise serializers.ValidationError(f"{color_key} must be a #RRGGBB hex color.")
                cleaned[color_key] = color
        return cleaned


class EnrollThemeSerializer(serializers.Serializer):
    """Resolved theme block nested in the public GET /enroll/{token} response."""

    template_key = serializers.CharField()
    cover_image_url = serializers.CharField(allow_blank=True)
    bg_color = serializers.CharField(allow_blank=True)
    accent_color = serializers.CharField(allow_blank=True)
    button_text_color = serializers.CharField(allow_blank=True)
    font = serializers.CharField()
    welcome_body = serializers.CharField(allow_blank=True)
    fields_config = serializers.JSONField()
    qr_style = serializers.JSONField()
    terms_url = serializers.CharField(allow_blank=True)
    privacy_url = serializers.CharField(allow_blank=True)
