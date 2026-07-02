"""Coupon / promotion serializers (Phase 11)."""

from __future__ import annotations

from rest_framework import serializers

from billing.coupons import normalize
from billing.models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "type",
            "value",
            "plan_scope",
            "max_redemptions",
            "per_merchant_once",
            "expires_at",
            "active",
            "redemption_count",
            "created_at",
        ]
        read_only_fields = ["redemption_count", "created_at"]


class CouponCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "type",
            "value",
            "plan_scope",
            "max_redemptions",
            "per_merchant_once",
            "expires_at",
            "active",
        ]

    def validate_code(self, value: str) -> str:
        code = normalize(value)
        if not code:
            raise serializers.ValidationError("Code is required.")
        if Coupon.objects.filter(code=code).exists():
            raise serializers.ValidationError("A coupon with this code already exists.")
        return code


class CouponUpdateSerializer(serializers.ModelSerializer):
    """Only the safe-to-change fields after creation (never code/type/value)."""

    class Meta:
        model = Coupon
        fields = ["active", "expires_at", "max_redemptions", "plan_scope", "per_merchant_once"]


class CouponRedemptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    merchant = serializers.DictField()
    discount_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    detail = serializers.CharField()
    created_at = serializers.DateTimeField()


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
