"""Cross-tenant invoice queries for the admin console (Phase 5).

Deliberately NOT tenant-scoped — the admin sees every merchant's invoices.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from billing.models import Invoice


def invoice_queryset() -> QuerySet[Invoice]:
    return Invoice.objects.select_related("merchant").order_by("-issued_at")


def apply_filters(qs: QuerySet[Invoice], params: Any) -> QuerySet[Invoice]:
    """status, merchant_id, and an issued_at [from, to] date range."""
    status = (params.get("status") or "").strip().lower()
    if status:
        qs = qs.filter(status=status)
    merchant_id = (params.get("merchant_id") or "").strip()
    if merchant_id:
        qs = qs.filter(merchant_id=merchant_id)
    date_from = (params.get("from") or "").strip()
    if date_from:
        qs = qs.filter(issued_at__date__gte=date_from)
    date_to = (params.get("to") or "").strip()
    if date_to:
        qs = qs.filter(issued_at__date__lte=date_to)
    return qs


def row(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "merchant": {
            "id": invoice.merchant_id,
            "name": invoice.merchant.name,
            "slug": invoice.merchant.slug,
        },
        "amount_egp": invoice.amount_egp,
        "status": invoice.status,
        "provider": invoice.provider,
        "issued_at": invoice.issued_at,
    }


def detail(invoice: Invoice) -> dict:
    return {
        **row(invoice),
        "gateway_ref": invoice.gateway_ref,
        "pdf_url": invoice.pdf_url,
        "note": invoice.note,
        "created_at": invoice.created_at,
    }
