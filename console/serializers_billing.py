"""Dunning + reconciliation serializers (Phase 5)."""

from __future__ import annotations

from rest_framework import serializers


class _MerchantRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()


class _LastFailedInvoiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    amount_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    issued_at = serializers.DateTimeField()


class DunningRowSerializer(serializers.Serializer):
    merchant = _MerchantRefSerializer()
    plan = serializers.CharField()
    current_period_end = serializers.DateTimeField(allow_null=True)
    last_failed_invoice = _LastFailedInvoiceSerializer(allow_null=True)


class NotifyRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class NotifyResponseSerializer(serializers.Serializer):
    sent = serializers.BooleanField()


class _StalePendingInvoiceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    merchant = _MerchantRefSerializer()
    amount_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    issued_at = serializers.DateTimeField()
    note = serializers.CharField(allow_blank=True)


class _ActiveWithoutPaidSerializer(serializers.Serializer):
    merchant = _MerchantRefSerializer()
    plan = serializers.CharField()
    provider = serializers.CharField(allow_blank=True)


class ReconciliationSerializer(serializers.Serializer):
    stale_pending_invoices = _StalePendingInvoiceSerializer(many=True)
    active_without_paid_invoice = _ActiveWithoutPaidSerializer(many=True)
