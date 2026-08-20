"""Serializers for the Platform Operations console (Phase 14)."""

from __future__ import annotations

from typing import Any, ClassVar

from django_celery_results.models import TaskResult
from rest_framework import serializers

from billing.models import WebhookDelivery
from console.models import FeatureFlag, FeatureFlagOverride, PlatformSetting
from wallets.models import WalletSyncFailure


class FeatureFlagOverrideSerializer(serializers.ModelSerializer):
    merchant_id = serializers.UUIDField(source="merchant.id", read_only=True)

    class Meta:
        model = FeatureFlagOverride
        fields = ["merchant_id", "enabled"]


class FeatureFlagSerializer(serializers.ModelSerializer):
    overrides = FeatureFlagOverrideSerializer(many=True, read_only=True)

    class Meta:
        model = FeatureFlag
        fields = [
            "key",
            "label",
            "description",
            "enabled",
            "overrides",
            "updated_by_email",
            "updated_at",
        ]
        read_only_fields = ["updated_by_email", "updated_at"]
        # Drop the auto unique-validator so the view returns a clean 409 envelope
        # on a duplicate key instead of a 400 field error.
        extra_kwargs: ClassVar[dict[str, Any]] = {"key": {"validators": []}}


class OverrideInputSerializer(serializers.Serializer):
    """Set/clear one merchant's override of a flag."""

    merchant_id = serializers.UUIDField()
    enabled = serializers.BooleanField()


class PlatformSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSetting
        fields = ["key", "value", "description", "updated_by_email", "updated_at"]
        read_only_fields = ["updated_by_email", "updated_at"]


class MaintenanceSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    message = serializers.CharField(allow_blank=True, required=False, default="")


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "provider",
            "kind",
            "gateway_ref",
            "merchant_id_hint",
            "status",
            "error",
            "payload",
            "created_at",
            "processed_at",
        ]


class WalletSyncFailureSerializer(serializers.ModelSerializer):
    customer_card_id = serializers.UUIDField(read_only=True)
    merchant_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = WalletSyncFailure
        fields = [
            "id",
            "customer_card_id",
            "merchant_id",
            "platform",
            "operation",
            "error",
            "resolved",
            "created_at",
            "resolved_at",
        ]


class TaskResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskResult
        fields = [
            "task_id",
            "task_name",
            "status",
            "worker",
            "date_created",
            "date_done",
            "result",
            "traceback",
        ]
