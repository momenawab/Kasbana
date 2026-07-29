"""Cross-tenant merchant queries for the admin console.

Deliberately NOT tenant-scoped — the admin sees every merchant. Annotates the
counts the directory + detail views need in one query to avoid N+1s.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet

from core.enums import Role, WalletPlatform
from core.models import CustomerCard, Merchant, StaffUser, WalletRegistration


def real_merchants() -> QuerySet[Merchant]:
    """Every *real* merchant — demo/sales accounts excluded.

    Demo merchants exist only to render a prospect's branded wallet pass in the
    console's test-card tool (``console.demo_cards``). They are not customers, so
    every console surface that counts, ranks or reviews merchants starts here
    rather than at ``Merchant.objects`` — otherwise a sales demo would inflate
    signup counts, revenue cohorts and the lifecycle board.
    """
    return Merchant.objects.exclude(is_demo=True)


def merchant_queryset() -> QuerySet[Merchant]:
    """All merchants with directory aggregates annotated (cross-tenant)."""
    return (
        real_merchants()
        .annotate(
            cards_count=Count("cards", distinct=True),
            customers_count=Count("customer_cards", distinct=True),
            staff_count=Count("staff", distinct=True),
            locations_count=Count("locations", distinct=True),
        )
        .order_by("-created_at")
    )


def apply_filters(qs: QuerySet[Merchant], params: Any) -> QuerySet[Merchant]:
    """Directory search/filter: q (name/slug/legal), status, plan."""
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q) | Q(legal_name__icontains=q))
    status = (params.get("status") or "").strip().upper()
    if status:
        qs = qs.filter(status=status)
    plan = (params.get("plan") or "").strip().upper()
    if plan:
        qs = qs.filter(plan=plan)
    return qs


def owner_contact(merchant: Merchant) -> dict[str, str]:
    """The merchant's owner (email/name) — best-effort from the OWNER StaffUser."""
    owner = (
        StaffUser.objects.filter(merchant=merchant, role=Role.OWNER, is_active=True)
        .select_related("user")
        .first()
    )
    if owner is None:
        return {"email": "", "name": ""}
    user = owner.user
    return {"email": user.email, "name": user.get_full_name() or ""}


def wallet_counts(merchant: Merchant) -> dict[str, int]:
    regs = WalletRegistration.objects.filter(customer_card__merchant=merchant, is_active=True)
    return {
        "apple": regs.filter(platform=WalletPlatform.APPLE).count(),
        "google": regs.filter(platform=WalletPlatform.GOOGLE).count(),
    }


def customers_count(merchant: Merchant) -> int:
    return CustomerCard.objects.filter(merchant=merchant).count()
