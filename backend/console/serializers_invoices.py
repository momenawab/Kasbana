"""Invoice + manual-invoice serializers (Phase 5)."""

from __future__ import annotations

from rest_framework import serializers

from billing.models import InvoiceStatus


class _InvoiceMerchantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()


class InvoiceListSerializer(serializers.Serializer):
    """One row in the admin invoice list — cross-tenant, so the merchant is inline."""

    id = serializers.UUIDField()
    merchant = _InvoiceMerchantSerializer()
    amount_egp = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    provider = serializers.CharField(allow_blank=True)
    issued_at = serializers.DateTimeField()


class InvoiceDetailSerializer(InvoiceListSerializer):
    gateway_ref = serializers.CharField(allow_blank=True)
    pdf_url = serializers.CharField(allow_blank=True)
    note = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()


class ManualInvoiceCreateSerializer(serializers.Serializer):
    """POST /merchants/{id}/invoices — a one-off invoice for an offline payment
    (``status="paid"``, the default) or an expected-but-not-yet-received one
    (``status="pending"``)."""

    amount_egp = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    status = serializers.ChoiceField(
        choices=[InvoiceStatus.PAID, InvoiceStatus.PENDING], default=InvoiceStatus.PAID
    )
    note = serializers.CharField(required=False, allow_blank=True)
