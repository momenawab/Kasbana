"""Partner / referral-program serializers (Phase E.1)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from core.models import Merchant
from partners.models import Partner, PartnerProgramConfig, PartnerReferral


def _merchant_brief(merchant: Merchant) -> dict[str, Any]:
    # str(id) keeps the dict JSON-safe when embedded in audit before/after.
    return {"id": str(merchant.id), "name": merchant.name, "slug": merchant.slug}


class PartnerProgramConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerProgramConfig
        fields = ["enabled", "partner_free_months", "merchant_free_months"]


class PartnerSerializer(serializers.ModelSerializer):
    merchant = serializers.SerializerMethodField()
    resolved = serializers.SerializerMethodField()
    referral_count = serializers.SerializerMethodField()
    converted_count = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = [
            "id",
            "merchant",
            "code",
            "active",
            "enabled_override",
            "partner_free_months_override",
            "merchant_free_months_override",
            "resolved",
            "referral_count",
            "converted_count",
            "created_at",
        ]

    def get_merchant(self, obj: Partner) -> dict[str, Any]:
        return _merchant_brief(obj.merchant)

    def get_resolved(self, obj: Partner) -> dict[str, Any]:
        cfg = obj.resolved_config()
        return {
            "enabled": cfg.enabled,
            "partner_free_months": cfg.partner_free_months,
            "merchant_free_months": cfg.merchant_free_months,
        }

    def get_referral_count(self, obj: Partner) -> int:
        count = getattr(obj, "referral_count_annotated", None)
        return count if count is not None else obj.referrals.count()

    def get_converted_count(self, obj: Partner) -> int:
        count = getattr(obj, "converted_count_annotated", None)
        return count if count is not None else obj.referrals.filter(reward_granted=True).count()


class PartnerCreateSerializer(serializers.Serializer):
    """Enrol an existing merchant as a partner with a unique code."""

    merchant_id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    active = serializers.BooleanField(required=False, default=True)
    enabled_override = serializers.BooleanField(required=False, allow_null=True)
    partner_free_months_override = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    merchant_free_months_override = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("Code is required.")
        if Partner.objects.filter(code__iexact=code).exists():
            raise serializers.ValidationError("A partner with this code already exists.")
        return code

    def validate_merchant_id(self, value: Any) -> Merchant:
        merchant = Merchant.objects.filter(pk=value).first()
        if merchant is None:
            raise serializers.ValidationError("Unknown merchant.")
        if Partner.objects.filter(merchant=merchant).exists():
            raise serializers.ValidationError("This merchant is already a partner.")
        return merchant

    def create(self, validated_data: dict[str, Any]) -> Partner:
        merchant = validated_data.pop("merchant_id")
        return Partner.objects.create(merchant=merchant, **validated_data)


class PartnerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            "code",
            "active",
            "enabled_override",
            "partner_free_months_override",
            "merchant_free_months_override",
        ]
        extra_kwargs = {"code": {"required": False}}

    def validate_code(self, value: str) -> str:
        code = (value or "").strip()
        if not code:
            raise serializers.ValidationError("Code is required.")
        qs = Partner.objects.filter(code__iexact=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A partner with this code already exists.")
        return code


class PartnerReferralSerializer(serializers.ModelSerializer):
    referred_merchant = serializers.SerializerMethodField()

    class Meta:
        model = PartnerReferral
        fields = [
            "id",
            "referred_merchant",
            "attributed_via",
            "converted_at",
            "reward_granted",
            "partner_months_granted",
            "merchant_months_granted",
            "created_at",
        ]

    def get_referred_merchant(self, obj: PartnerReferral) -> dict[str, Any]:
        return _merchant_brief(obj.referred_merchant)


class AssignReferralSerializer(serializers.Serializer):
    merchant_id = serializers.UUIDField()
