"""Merchant directory + detail endpoints (Phase 2).

``GET /api/admin/v1/merchants`` — cross-tenant, searchable/filterable list.
``GET /api/admin/v1/merchants/{id}`` — the 360° view. Both read-only here; the
subscription/billing/support mutations arrive in later phases.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing import entitlements
from billing.services import subscription_for
from billing.wire import plan_to_wire
from common.pagination import DefaultCursorPagination
from console import merchants as m
from console.permissions import AdminAPIView
from console.serializers_merchants import MerchantDetailSerializer, MerchantListSerializer
from core.models import Merchant


class MerchantListView(AdminAPIView):
    """GET /merchants — cross-tenant directory (q/status/plan filters)."""

    @extend_schema(responses=MerchantListSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = m.apply_filters(m.merchant_queryset(), request.query_params)

        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self) or []
        rows = [self._row(mer) for mer in page]
        return paginator.get_paginated_response(MerchantListSerializer(rows, many=True).data)

    @staticmethod
    def _row(mer: Merchant) -> dict:
        sub = subscription_for(mer)
        return {
            "id": mer.id,
            "name": mer.name,
            "slug": mer.slug,
            "status": mer.status,
            "plan": plan_to_wire(sub),
            "billing_status": sub.status,
            "trial_ends_at": sub.trial_ends_at if sub.trial_active() else None,
            # Counts are annotated by merchant_queryset(); getattr keeps mypy happy.
            "cards_count": getattr(mer, "cards_count", 0),
            "customers_count": getattr(mer, "customers_count", 0),
            "staff_count": getattr(mer, "staff_count", 0),
            "locations_count": getattr(mer, "locations_count", 0),
            "created_at": mer.created_at,
        }


class MerchantDetailView(AdminAPIView):
    """GET /merchants/{id} — the 360° merchant view."""

    @extend_schema(responses=MerchantDetailSerializer)
    def get(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        sub = subscription_for(mer)
        settings = getattr(mer, "settings", None)
        meta = getattr(mer, "admin_meta", None)

        payload = {
            "id": mer.id,
            "name": mer.name,
            "slug": mer.slug,
            "legal_name": mer.legal_name,
            "status": mer.status,
            "plan": plan_to_wire(sub),
            "logo_url": mer.logo_url,
            "color_bg": mer.color_bg,
            "color_fg": mer.color_fg,
            "created_at": mer.created_at,
            "billing_status": sub.status,
            "trial_ends_at": sub.trial_ends_at,
            "current_period_end": sub.current_period_end,
            "provider": sub.provider,
            "owner": m.owner_contact(mer),
            # Business contact from MerchantSettings (email + phone-as-name label).
            "contact": {
                "email": getattr(settings, "contact_email", "") or "",
                "name": getattr(settings, "contact_phone", "") or "",  # phone shown as contact
            },
            "usage": entitlements.usage(mer),
            "wallet": m.wallet_counts(mer),
            "admin_meta": {
                "internal_notes": getattr(meta, "internal_notes", "") or "",
                "flags": getattr(meta, "flags", {}) or {},
                "account_manager_email": (
                    meta.account_manager.email if meta and meta.account_manager else None
                ),
            },
        }
        return Response(MerchantDetailSerializer(payload).data)
