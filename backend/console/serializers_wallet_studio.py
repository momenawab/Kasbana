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


class PassScaffoldSerializer(serializers.Serializer):
    """The card's current pass payloads, in a form an overlay can adopt.

    Same shape as the preview but token-preserving ({balance} rather than "3/8")
    and with the locked keys already removed, so a copy of it is directly
    editable and directly saveable.
    """

    apple = serializers.DictField(allow_null=True)
    google_class = serializers.DictField(allow_null=True)
    google_object = serializers.DictField(allow_null=True)
    errors = serializers.DictField()


class CardJsonSerializer(serializers.Serializer):
    """The whole card as one editable document.

    Four sections, because they are four different kinds of thing and collapsing
    them would hide which edits are risky:

    * ``card``   — the program itself (name, goal, reward, colours, image URLs).
      Editing ``stamps_required`` here changes the goal for every existing holder.
    * ``design`` — how the pass is rendered (template, stamp style, sizes, strip
      artwork). Everything the Editor tab writes.
    * ``apple_overlay`` / ``google_overlay`` — raw pass payload merged last.

    ``platform`` is read-only: the identity keys the platform owns, echoed back
    so the document shows the complete pass rather than looking half-missing.
    """

    card = serializers.DictField(required=False)
    design = serializers.DictField(required=False)
    apple_overlay = serializers.DictField(required=False)
    google_overlay = serializers.DictField(required=False)
    platform = serializers.DictField(read_only=True)
    assets = serializers.ListField(child=serializers.DictField(), read_only=True)


class RepublishResultSerializer(serializers.Serializer):
    """How many live passes a republish touched."""

    customer_cards = serializers.IntegerField()
    google_class_synced = serializers.BooleanField()
