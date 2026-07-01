"""Invoice endpoints (Phase 5).

``GET /invoices`` — cross-tenant list (status/merchant/date filters).
``GET /invoices/{id}`` — detail. ``POST /invoices/{id}/retry`` — re-attempt a
FAILED charge via a fresh gateway checkout. ``POST /merchants/{id}/invoices``
— a manual/one-off invoice (the mark-paid path for an offline payment).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing import services
from billing.models import Invoice, InvoiceStatus
from billing.serializers import CheckoutResponseSerializer
from console import audit
from console import invoices as inv
from console.merchants import owner_contact
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_invoices import (
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    ManualInvoiceCreateSerializer,
)
from core.models import Merchant


class InvoiceListView(AdminAPIView):
    """GET /invoices — cross-tenant, filter by status/merchant_id/from/to."""

    @extend_schema(responses=InvoiceListSerializer(many=True))
    def get(self, request: Request) -> Response:
        from common.pagination import DefaultCursorPagination

        qs = inv.apply_filters(inv.invoice_queryset(), request.query_params)
        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self) or []
        rows = [inv.row(i) for i in page]
        return paginator.get_paginated_response(InvoiceListSerializer(rows, many=True).data)


class InvoiceDetailView(AdminAPIView):
    """GET /invoices/{id} — full detail incl. gateway ref/note."""

    @extend_schema(responses=InvoiceDetailSerializer)
    def get(self, request: Request, invoice_id: str) -> Response:
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        return Response(InvoiceDetailSerializer(inv.detail(invoice)).data)


class InvoiceRetryView(AdminAPIView):
    """POST /invoices/{id}/retry — only for a FAILED invoice."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=None, responses=CheckoutResponseSerializer)
    def post(self, request: Request, invoice_id: str) -> Response:
        invoice = get_object_or_404(Invoice, pk=invoice_id)
        if invoice.status != InvoiceStatus.FAILED:
            return Response(
                {
                    "error": {
                        "code": "INVOICE_NOT_FAILED",
                        "message": "Only a FAILED invoice can be retried.",
                    }
                },
                status=409,
            )
        session = services.retry_invoice(
            invoice, customer_email=owner_contact(invoice.merchant)["email"]
        )
        audit.record(
            request,
            "invoice.retry",
            target_type="invoice",
            target_id=str(invoice.id),
            metadata={
                "merchant_id": str(invoice.merchant_id),
                "checkout_url": session.checkout_url,
            },
        )
        return Response({"checkout_url": session.checkout_url})


class MerchantInvoiceCreateView(AdminAPIView):
    """POST /merchants/{id}/invoices — a manual/one-off invoice (mark-paid for
    an offline payment, or a pending expected one)."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=ManualInvoiceCreateSerializer, responses=InvoiceDetailSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = ManualInvoiceCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        invoice = services.record_invoice(
            merchant,
            amount_egp=data["amount_egp"],
            status=data["status"],
            note=data.get("note", ""),
        )
        audit.record(
            request,
            "invoice.create_manual",
            target_type="invoice",
            target_id=str(invoice.id),
            metadata={
                "merchant_id": str(merchant.id),
                "amount_egp": str(invoice.amount_egp),
                "status": invoice.status,
                "note": invoice.note,
            },
        )
        return Response(InvoiceDetailSerializer(inv.detail(invoice)).data, status=201)
