"""Merchant directory + 360° detail serializers (Phase 2)."""

from __future__ import annotations

from rest_framework import serializers


class MerchantListSerializer(serializers.Serializer):
    """One row in the admin merchant directory."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    status = serializers.CharField()  # merchant status (ACTIVE/SUSPENDED)
    plan = serializers.CharField()  # wire plan (trial/starter/growth/chain)
    billing_status = serializers.CharField()  # trialing/active/locked…
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    cards_count = serializers.IntegerField()
    customers_count = serializers.IntegerField()
    staff_count = serializers.IntegerField()
    locations_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class _ContactSerializer(serializers.Serializer):
    email = serializers.CharField(allow_blank=True)
    name = serializers.CharField(allow_blank=True)


class _WalletCountsSerializer(serializers.Serializer):
    apple = serializers.IntegerField()
    google = serializers.IntegerField()


class _AdminMetaSerializer(serializers.Serializer):
    internal_notes = serializers.CharField(allow_blank=True)
    flags = serializers.DictField()
    account_manager_email = serializers.CharField(allow_blank=True, allow_null=True)


class MerchantUpdateSerializer(serializers.Serializer):
    """Editable merchant-profile fields (admin). All optional — a PATCH sends
    only what changed. ``name`` lives on ``Merchant``; the contact pair lives on
    ``MerchantSettings`` (the sidecar)."""

    name = serializers.CharField(max_length=120, required=False)
    legal_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        # ``name`` is the merchant's display identity — never let it be blanked.
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        return value.strip()


class MerchantDetailSerializer(serializers.Serializer):
    """The 360° merchant view for the admin console."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    legal_name = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    plan = serializers.CharField()
    logo_url = serializers.CharField(allow_blank=True)
    color_bg = serializers.CharField(allow_blank=True)
    color_fg = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()

    # Subscription snapshot
    billing_status = serializers.CharField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    current_period_end = serializers.DateTimeField(allow_null=True)
    provider = serializers.CharField(allow_blank=True)

    # Owner + usage
    owner = _ContactSerializer()
    contact = _ContactSerializer()
    usage = serializers.DictField()
    wallet = _WalletCountsSerializer()

    # Admin metadata (sidecar)
    admin_meta = _AdminMetaSerializer()
