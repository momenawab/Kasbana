"""Wire formats for the admin Wallet Studio.

The design payload itself is ``wallets.serializers.AdminWalletCardDesignSerializer``
— reused rather than restated, so the admin console and the merchant dashboard
validate the same design against the same rules (the admin one simply adds the
raw pass-JSON overlays and skips the template allowlist).
"""

from __future__ import annotations

from rest_framework import serializers


class MerchantCardRowSerializer(serializers.Serializer):
    """One of a merchant's cards, as listed in the studio's left rail."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    stamps_required = serializers.IntegerField()
    reward_title = serializers.CharField(allow_blank=True)
    color_bg = serializers.CharField(allow_blank=True)
    color_fg = serializers.CharField(allow_blank=True)
    logo_url = serializers.CharField(allow_blank=True)
    template_key = serializers.CharField(allow_blank=True)
    # Whether an admin has authored raw pass JSON for this card — the rail badges
    # it, so a bespoke card is recognisable without opening it.
    has_overlay = serializers.BooleanField()
    customers_count = serializers.IntegerField()


class PassPreviewRequestSerializer(serializers.Serializer):
    """Dry-run a design without saving it.

    ``design`` is an optional unsaved candidate: the studio posts the editor's
    current state so an admin sees the result — and any validation error — before
    committing. Omit it to preview exactly what is stored.
    """

    design = serializers.DictField(required=False)
    stamp_count = serializers.IntegerField(required=False, min_value=0, allow_null=True)


class PassPreviewSerializer(serializers.Serializer):
    """The payloads a card renders for one sample balance."""

    stamp_count = serializers.IntegerField()
    stamps_required = serializers.IntegerField()
    # Free-form: these are literally the pass payloads, whose shape is Apple's and
    # Google's, not ours. Nullable so one broken side still returns the other.
    apple = serializers.DictField(allow_null=True)
    google_class = serializers.DictField(allow_null=True)
    google_object = serializers.DictField(allow_null=True)
    errors = serializers.DictField()


class RepublishResultSerializer(serializers.Serializer):
    """How many live passes a republish touched."""

    customer_cards = serializers.IntegerField()
    google_class_synced = serializers.BooleanField()
