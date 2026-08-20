"""Coupon / promotion serializers (Phase 11)."""

from __future__ import annotations

from rest_framework import serializers

from billing.coupons import normalize
from billing.models import Coupon, CouponGroup


class CouponGroupSerializer(serializers.ModelSerializer):
    coupon_count = serializers.SerializerMethodField()

    class Meta:
        model = CouponGroup
        fields = ["id", "name", "description", "active", "coupon_count", "created_at"]
        read_only_fields = ["created_at"]

    def get_coupon_count(self, obj: CouponGroup) -> int:
        # Use the queryset annotation when present (list view); otherwise count
        # directly so single-object responses (create/detail) work too.
        annotated = getattr(obj, "coupon_count_annotated", None)
        if annotated is not None:
            return annotated
        return obj.coupons.count()


class CouponGroupWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CouponGroup
        fields = ["name", "description", "active"]

    def validate_name(self, value: str) -> str:
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Name is required.")
        return name


class CouponSerializer(serializers.ModelSerializer):
    # Render the group pk as a UUID *string* (like ``id``) rather than a raw UUID
    # object, so the serialized dict stays JSON-safe when embedded in audit
    # metadata (before/after snapshots).
    group = serializers.PrimaryKeyRelatedField(
        queryset=CouponGroup.objects.all(),
        allow_null=True,
        required=False,
        pk_field=serializers.UUIDField(format="hex_verbose"),
    )

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
            "group",
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
            "group",
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
        fields = [
            "active",
            "expires_at",
            "max_redemptions",
            "plan_scope",
            "per_merchant_once",
            "group",
        ]


class CouponRedemptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    merchant = serializers.DictField()
    discount_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    detail = serializers.CharField()
    created_at = serializers.DateTimeField()


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
