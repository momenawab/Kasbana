"""Test-card (demo) serializers — the console's sales pitch tool."""

from __future__ import annotations

from rest_framework import serializers


class DemoCardCreateSerializer(serializers.Serializer):
    """The Card Designer's fields, plus the prospect's business name.

    ``merchant_name`` is free text on purpose: the whole point is to brand a pass
    for a business that has not signed up yet, so it never resolves to a real
    merchant record.
    """

    merchant_name = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=120)
    type = serializers.ChoiceField(choices=["STAMP", "POINTS"], default="STAMP")
    stamps_required = serializers.IntegerField(min_value=1, max_value=30, default=8)
    reward_title = serializers.CharField(max_length=120)
    reward_description = serializers.CharField(required=False, allow_blank=True, default="")
    color_bg = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")
    color_fg = serializers.CharField(max_length=7, required=False, allow_blank=True, default="")
    logo_url = serializers.URLField(required=False, allow_blank=True, default="")
    hero_image_url = serializers.URLField(required=False, allow_blank=True, default="")
    single_use = serializers.BooleanField(required=False, default=False)
    referral_enabled = serializers.BooleanField(required=False, default=False)
    # Pre-fill the demo pass with a few stamps so it looks used in the pitch.
    preview_stamps = serializers.IntegerField(min_value=0, max_value=30, required=False, default=0)

    def validate_merchant_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Business name is required.")
        return value.strip()


class DemoCardSerializer(serializers.Serializer):
    """A demo card row / creation result."""

    merchant_id = serializers.UUIDField()
    card_id = serializers.UUIDField()
    customer_card_id = serializers.UUIDField(allow_null=True)
    merchant_name = serializers.CharField()
    card_name = serializers.CharField()
    enroll_token = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    # Present on create + the pass endpoint; null when wallet creds are absent.
    apple_pass_url = serializers.CharField(allow_null=True, required=False)
    google_save_url = serializers.CharField(allow_null=True, required=False)


class DemoCardPassSerializer(serializers.Serializer):
    """Add-to-wallet URLs for an existing demo card."""

    apple_pass_url = serializers.CharField(allow_null=True)
    google_save_url = serializers.CharField(allow_null=True)
