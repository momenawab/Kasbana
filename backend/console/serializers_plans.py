"""Plan catalogue serializers (Phase 3)."""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "key",
            "name",
            "price_egp",
            "price_egp_annual",
            "is_public",
            "archived",
            # Pasted in by ops after `manage.py create_paymob_plans` (per env).
            "paymob_plan_id_monthly",
            "paymob_plan_id_annual",
            "max_cards",
            "max_locations",
            "max_staff",
            "max_customers",
            "export",
            "api",
            "specialized_roles",
            "custom_branding",
            "referral",
            "automations",
            "analytics",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class PlanUpdateSerializer(PlanSerializer):
    """Same shape as ``PlanSerializer`` but ``key`` can't be changed after creation."""

    class Meta(PlanSerializer.Meta):
        read_only_fields = [*PlanSerializer.Meta.read_only_fields, "key"]
