"""Dashboard serializers (contract §3.6 — snake_case JSON keys).

Merchant-facing configuration + analytics. All writes are scoped to the
caller's merchant in the views (``perform_create`` sets ``merchant``); these
serializers never accept a client-supplied ``merchant``.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.models import StaffInvite
from core.enums import LedgerEvent, Role
from core.models import Card, CustomerCard, Location, StaffUser
from core.tenancy import get_request_merchant

User = get_user_model()


class CardSerializer(serializers.ModelSerializer):
    """Card (program template) CRUD. ``google_class_id`` is provisioning output."""

    holders = serializers.SerializerMethodField()
    stamps_issued = serializers.SerializerMethodField()
    rewards_redeemed = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = [
            "id",
            "type",
            "name",
            "stamps_required",
            "reward_title",
            "reward_description",
            "color_bg",
            "color_fg",
            "logo_url",
            "hero_image_url",
            "single_use",
            "referral_enabled",
            "google_class_id",
            "status",
            "holders",
            "stamps_issued",
            "rewards_redeemed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "google_class_id", "created_at", "updated_at"]

    def get_holders(self, obj: Card) -> int:
        return getattr(obj, "holders", obj.customer_cards.count())

    def get_stamps_issued(self, obj: Card) -> int:
        if hasattr(obj, "stamps_issued"):
            return obj.stamps_issued
        from core.models import StampLedger

        return StampLedger.objects.filter(
            customer_card__card=obj, event_type=LedgerEvent.STAMP
        ).count()

    def get_rewards_redeemed(self, obj: Card) -> int:
        if hasattr(obj, "rewards_redeemed"):
            return obj.rewards_redeemed
        from core.models import Redemption

        return Redemption.objects.filter(reward__card=obj).count()


class CardStatsSerializer(serializers.Serializer):
    """GET /cards/{id}/stats response."""

    holders = serializers.IntegerField()
    stamps_issued = serializers.IntegerField()
    rewards_redeemed = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    apple_count = serializers.IntegerField()
    google_count = serializers.IntegerField()


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "address", "lat", "lng", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class LocationStatsSerializer(serializers.Serializer):
    stamps = serializers.IntegerField()
    redemptions = serializers.IntegerField()
    customers = serializers.IntegerField()


class StaffSerializer(serializers.ModelSerializer):
    """Read representation of a staff member."""

    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    location_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = StaffUser
        fields = ["id", "name", "email", "role", "location_id", "is_active"]
        read_only_fields = fields

    def get_name(self, obj: StaffUser) -> str:
        return obj.user.get_full_name() or obj.user.email


class StaffCreateSerializer(serializers.Serializer):
    """POST /staff — create the auth User + StaffUser in one transaction."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Role.choices)
    location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False, allow_null=True
    )

    def validate_email(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_location(self, value: Location | None) -> Location | None:
        if value is not None:
            merchant = get_request_merchant(self.context["request"])
            if value.merchant_id != getattr(merchant, "id", None):
                raise serializers.ValidationError("Location not found for this merchant.")
        return value

    def create(self, validated_data: dict[str, Any]) -> StaffUser:
        merchant = get_request_merchant(self.context["request"])
        with transaction.atomic():
            user = User(username=validated_data["email"], email=validated_data["email"])
            user.set_password(validated_data["password"])
            user.save()
            return StaffUser.objects.create(
                merchant=merchant,
                user=user,
                role=validated_data["role"],
                location=validated_data.get("location"),
            )

    def to_representation(self, instance: StaffUser) -> dict[str, Any]:
        return StaffSerializer(instance).data


class StaffWriteSerializer(serializers.ModelSerializer):
    """PATCH /staff/{id} — role / location / active only."""

    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), source="location", required=False, allow_null=True
    )

    class Meta:
        model = StaffUser
        fields = ["role", "location_id", "is_active"]

    def validate_location_id(self, value: Location | None) -> Location | None:
        if value is not None:
            merchant = get_request_merchant(self.context["request"])
            if value.merchant_id != getattr(merchant, "id", None):
                raise serializers.ValidationError("Location not found for this merchant.")
        return value


class StaffInviteSerializer(serializers.ModelSerializer):
    """POST /staff/invite — create a pending StaffInvite."""

    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), source="location", required=False, allow_null=True
    )

    class Meta:
        model = StaffInvite
        fields = ["email", "role", "location_id"]

    def validate_location_id(self, value: Location | None) -> Location | None:
        if value is not None:
            merchant = get_request_merchant(self.context["request"])
            if value.merchant_id != getattr(merchant, "id", None):
                raise serializers.ValidationError("Location not found for this merchant.")
        return value


class AnalyticsSummarySerializer(serializers.Serializer):
    """GET /analytics/summary response (contract §3.6)."""

    enrollments = serializers.IntegerField()
    active_cards = serializers.IntegerField()
    redemptions = serializers.IntegerField()
    apple_count = serializers.IntegerField()
    google_count = serializers.IntegerField()
    repeat_rate = serializers.FloatField()


class CustomerSerializer(serializers.ModelSerializer):
    """Read representation for GET /customers and GET /customers/{id}."""

    card_name = serializers.CharField(source="card.name", read_only=True)
    stamps_required = serializers.IntegerField(source="card.stamps_required", read_only=True)
    wallet_platform = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCard
        fields = [
            "id",
            "card",
            "card_name",
            "customer_phone",
            "customer_name",
            "customer_email",
            "stamp_count",
            "stamps_required",
            "wallet_platform",
            "status",
            "birthday",
            "consent_at",
            "last_event_at",
            "enrolled_at",
        ]
        read_only_fields = fields

    def get_wallet_platform(self, obj: CustomerCard) -> str | None:
        # List view prefetches active regs into ``active_wallet_regs`` (read in
        # Python, no query). Detail view has no prefetch → fall back to a query.
        regs = getattr(obj, "active_wallet_regs", None)
        if regs is not None:
            return regs[0].platform if regs else None
        reg = obj.wallet_registrations.filter(is_active=True).first()
        return reg.platform if reg else None


class TimelineEventSerializer(serializers.Serializer):
    """Customer timeline event (contract §3.6)."""

    event_type = serializers.ChoiceField(
        choices=[
            ("enroll", "enroll"),
            ("stamp", "stamp"),
            ("redeem", "redeem"),
            ("message", "message"),
        ]
    )
    delta = serializers.IntegerField(allow_null=True)
    balance_after = serializers.IntegerField(allow_null=True)
    staff_name = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)
    gps = serializers.CharField(allow_null=True)
    at = serializers.DateTimeField()


class UploadRequestSerializer(serializers.Serializer):
    """POST /uploads request (multipart)."""

    file = serializers.FileField()


class UploadSerializer(serializers.Serializer):
    """POST /uploads response."""

    url = serializers.URLField()


class CardQRSerializer(serializers.Serializer):
    """GET /cards/{id}/qr response."""

    join_url = serializers.URLField()
    qr_svg = serializers.CharField()
    poster_pdf_url = serializers.CharField(allow_blank=True)


class TimeseriesPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    value = serializers.IntegerField()


class TimeseriesResponseSerializer(serializers.Serializer):
    points = TimeseriesPointSerializer(many=True)


class RetentionPointSerializer(serializers.Serializer):
    day = serializers.IntegerField()
    retained_pct = serializers.FloatField()


class RetentionResponseSerializer(serializers.Serializer):
    curve = RetentionPointSerializer(many=True)
    at_risk_count = serializers.IntegerField()


class LocationStatSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    name = serializers.CharField()
    stamps = serializers.IntegerField()
    redemptions = serializers.IntegerField()


class ByLocationResponseSerializer(serializers.Serializer):
    results = LocationStatSerializer(many=True)


class ActivityItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=[("join", "join"), ("stamp", "stamp"), ("redeem", "redeem")]
    )
    actor_name = serializers.CharField(allow_null=True)
    customer_name = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)
    at = serializers.DateTimeField()


class ActivityResponseSerializer(serializers.Serializer):
    results = ActivityItemSerializer(many=True)
