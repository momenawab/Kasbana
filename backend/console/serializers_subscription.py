"""Subscription management serializers (Phase 4)."""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Subscription
from billing.plans import BillingInterval, BillingStatus
from console.models import AdminAuditLog
from core.enums import PlanTier


class SubscriptionSerializer(serializers.ModelSerializer):
    effective_plan = serializers.SerializerMethodField()
    # ``plan`` reads ENTERPRISE for every negotiated merchant, which says
    # nothing about the deal — these say which one, so the admin isn't left
    # cross-referencing the catalogue to answer "what are they actually on?".
    enterprise_plan_key = serializers.SerializerMethodField()
    enterprise_plan_name = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "enterprise_plan_key",
            "enterprise_plan_name",
            "billing_interval",
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

    def get_enterprise_plan_key(self, sub: Subscription) -> str:
        return sub.enterprise_plan.key if sub.enterprise_plan else ""

    def get_enterprise_plan_name(self, sub: Subscription) -> str:
        return sub.enterprise_plan.name if sub.enterprise_plan else ""


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


class AssignEnterpriseSerializer(serializers.Serializer):
    """POST body — put a merchant on a negotiated Enterprise plan (§12).

    ``plan_key`` rather than a ``PlanTier``: the tier is always ENTERPRISE, and
    what an admin is choosing is *which* plan (Enterprise Gold, …).
    """

    plan_key = serializers.CharField(max_length=32)
    interval = serializers.ChoiceField(
        choices=BillingInterval.choices, required=False, default=BillingInterval.MONTHLY
    )
    reason = serializers.CharField(max_length=500)


class EnterpriseAssignmentSerializer(serializers.Serializer):
    """What an admin sees after assigning: the deal, and how to get them to pay."""

    plan_key = serializers.CharField()
    plan_name = serializers.CharField()
    price_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    interval = serializers.CharField()
    subscription = SubscriptionSerializer()


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
