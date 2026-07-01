"""Dunning + reconciliation queries for the admin console (Phase 5).

Dunning: merchants whose subscription is ``PAST_DUE`` — a paying merchant's
renewal charge failed (see ``billing.services.apply_webhook_event``).

Reconciliation: internal consistency checks against data we actually control.
Live gateway-transaction-log matching against Paymob needs Paymob's reporting
API/export and real credentials — out of scope here (per the phase's own
"real Paymob creds" dependency); these checks catch what our own records can
already tell us is off, without depending on an unverified external API shape.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from billing.models import Invoice, InvoiceStatus, Subscription
from billing.plans import BillingStatus

STALE_PENDING_DAYS = 7


def dunning_queryset() -> QuerySet[Subscription]:
    return (
        Subscription.objects.filter(status=BillingStatus.PAST_DUE)
        .select_related("merchant")
        .order_by("updated_at")
    )


def dunning_row(sub: Subscription) -> dict:
    last_failed = (
        Invoice.objects.filter(merchant=sub.merchant, status=InvoiceStatus.FAILED)
        .order_by("-issued_at")
        .first()
    )
    return {
        "merchant": {"id": sub.merchant_id, "name": sub.merchant.name, "slug": sub.merchant.slug},
        "plan": sub.plan,
        "current_period_end": sub.current_period_end,
        "last_failed_invoice": (
            {
                "id": last_failed.id,
                "amount_egp": last_failed.amount_egp,
                "issued_at": last_failed.issued_at,
            }
            if last_failed
            else None
        ),
    }


def reconciliation_report() -> dict:
    stale_cutoff = timezone.now() - timedelta(days=STALE_PENDING_DAYS)
    stale_pending = (
        Invoice.objects.filter(
            status=InvoiceStatus.PENDING, gateway_ref="", issued_at__lt=stale_cutoff
        )
        .select_related("merchant")
        .order_by("issued_at")
    )

    # ACTIVE via a real gateway checkout (not comp/override, which never touch
    # provider) but no PAID invoice on record for that merchant.
    paid_merchant_ids = set(
        Invoice.objects.filter(status=InvoiceStatus.PAID).values_list("merchant_id", flat=True)
    )
    active_without_paid = (
        Subscription.objects.filter(status=BillingStatus.ACTIVE)
        .exclude(provider="")
        .exclude(merchant_id__in=paid_merchant_ids)
        .select_related("merchant")
        .order_by("-updated_at")
    )

    return {
        "stale_pending_invoices": [
            {
                "id": i.id,
                "merchant": {"id": i.merchant_id, "name": i.merchant.name, "slug": i.merchant.slug},
                "amount_egp": i.amount_egp,
                "issued_at": i.issued_at,
                "note": i.note,
            }
            for i in stale_pending
        ],
        "active_without_paid_invoice": [
            {
                "merchant": {
                    "id": sub.merchant_id,
                    "name": sub.merchant.name,
                    "slug": sub.merchant.slug,
                },
                "plan": sub.plan,
                "provider": sub.provider,
            }
            for sub in active_without_paid
        ],
    }
