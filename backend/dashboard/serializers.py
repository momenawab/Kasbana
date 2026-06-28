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

from core.enums import Role
from core.models import Card, CustomerCard, Location, StaffUser
from core.tenancy import get_request_merchant

User = get_user_model()


class CardSerializer(serializers.ModelSerializer):
    """Card (program template) CRUD. ``google_class_id`` is provisioning output."""

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
            "google_class_id",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "google_class_id", "created_at", "updated_at"]


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "address", "lat", "lng", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StaffSerializer(serializers.ModelSerializer):
    """Read representation of a staff member."""

    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = StaffUser
        fields = ["id", "email", "username", "role", "location", "is_active", "created_at"]
        read_only_fields = fields


class StaffCreateSerializer(serializers.Serializer):
    """POST /staff — create the auth User + StaffUser in one transaction.

    Request shape ({email, password, role, location?}) is NOT pinned by the
    contract (§3.6 only lists "GET/POST /staff"). Confirmed to match Momen's
    expectation; if the frontend onboarding differs, change it here.
    """

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
        # A staff member's location must belong to their own merchant.
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


class AnalyticsSummarySerializer(serializers.Serializer):
    """GET /analytics/summary response (contract §3.6)."""

    enrollments = serializers.IntegerField()
    active_cards = serializers.IntegerField()
    redemptions = serializers.IntegerField()
    apple_count = serializers.IntegerField()
    google_count = serializers.IntegerField()
    repeat_rate = serializers.FloatField()


class CustomerSerializer(serializers.ModelSerializer):
    """Read representation for the GET /customers list."""

    customer_card_id = serializers.UUIDField(source="id", read_only=True)
    card_name = serializers.CharField(source="card.name", read_only=True)

    class Meta:
        model = CustomerCard
        fields = [
            "customer_card_id",
            "card",
            "card_name",
            "customer_phone",
            "customer_name",
            "stamp_count",
            "status",
            "enrolled_at",
            "last_event_at",
        ]
        read_only_fields = fields
