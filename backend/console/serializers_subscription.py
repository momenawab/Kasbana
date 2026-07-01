"""Subscription management serializers (Phase 4)."""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Subscription
from billing.plans import BillingStatus
from console.models import AdminAuditLog
from core.enums import PlanTier


class SubscriptionSerializer(serializers.ModelSerializer):
    effective_plan = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "status",
            "trial_ends_at",
            "current_period_end",
            "provider",
            "comp",
            "override_plan",
            "override_expires_at",
            "notes",
            "effective_plan",
            "updated_at",
        ]

    def get_effective_plan(self, sub: Subscription) -> str | None:
        return sub.effective_plan()


class SubscriptionPatchSerializer(serializers.Serializer):
    """PATCH body — any subset of these; ``reason`` is always required."""

    plan = serializers.ChoiceField(choices=PlanTier.choices, required=False)
    status = serializers.ChoiceField(choices=BillingStatus.choices, required=False)
    override_plan = serializers.ChoiceField(
        choices=PlanTier.choices, required=False, allow_blank=True
    )
    override_expires_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(max_length=500)
    force = serializers.BooleanField(required=False, default=False)


class ExtendTrialSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CompSerializer(serializers.Serializer):
    on = serializers.BooleanField()
    reason = serializers.CharField(max_length=500)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class SubscriptionAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminAuditLog
        fields = ["actor_email", "action", "metadata", "created_at"]
