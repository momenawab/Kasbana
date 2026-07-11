"""Billing serializers (contract §3.6 — BillingState, Invoice, subscribe/cancel).

Money is EGP major units (``amount_egp`` / ``price_egp``). Plan/status are mapped
to their lowercase contract wire values via ``billing.wire``.
"""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Invoice
from core.enums import PlanTier


class PaymentMethodSerializer(serializers.Serializer):
    brand = serializers.CharField()
    last4 = serializers.CharField()


class UsageSerializer(serializers.Serializer):
    cards = serializers.IntegerField()
    locations = serializers.IntegerField()
    staff = serializers.IntegerField()
    customers = serializers.IntegerField()


class BillingStateSerializer(serializers.Serializer):
    plan = serializers.CharField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    price_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    usage = UsageSerializer()
    next_renewal = serializers.DateTimeField(allow_null=True)
    # Set when a merchant-initiated cancel is pending: access continues until
    # this date, then the plan locks. Null when no cancellation is scheduled.
    cancels_on = serializers.DateTimeField(allow_null=True, required=False)
    payment_method = PaymentMethodSerializer(allow_null=True)


class SubscribeRequestSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=[PlanTier.STARTER, PlanTier.GROWTH, PlanTier.CHAIN])
    # Optional discount code (Phase 11) — validated + applied server-side.
    coupon = serializers.CharField(required=False, allow_blank=True)

    def to_internal_value(self, data: dict) -> dict:
        # Contract sends lowercase plan values; map to the uppercase PlanTier.
        raw = dict(data)
        plan = str(raw.get("plan", "")).upper()
        raw["plan"] = plan
        return super().to_internal_value(raw)


class CheckoutResponseSerializer(serializers.Serializer):
    checkout_url = serializers.CharField()


class CancelRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class InvoiceSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["id", "date", "amount_egp", "status", "pdf_url"]

    def get_date(self, obj: Invoice) -> str:
        return obj.issued_at.date().isoformat()
