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

from accounts.models import MerchantSettings
from billing import entitlements
from billing.services import subscription_for
from billing.wire import plan_to_wire
from common.pagination import DefaultCursorPagination
from console import audit
from console import merchants as m
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_merchants import (
    MerchantDetailSerializer,
    MerchantListSerializer,
    MerchantUpdateSerializer,
)
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
    """GET /merchants/{id} — the 360° merchant view.

    PATCH edits the merchant's core profile (name / legal name / business
    contact). Reads are open to any admin (the base gate); the edit is gated on
    ``SUPPORT_TOOLS`` (super-admin + Support — an "account fix") and audited.
    """

    def get_permissions(self):  # type: ignore[no-untyped-def]
        # Reads stay open to any admin; only the edit needs the support gate.
        if self.request.method == "PATCH":
            return [IsAdminUser(), require(Permission.SUPPORT_TOOLS)()]
        return super().get_permissions()

    @extend_schema(responses=MerchantDetailSerializer)
    def get(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        return Response(MerchantDetailSerializer(self._detail_payload(mer)).data)

    @extend_schema(request=MerchantUpdateSerializer, responses=MerchantDetailSerializer)
    def patch(self, request: Request, merchant_id: str) -> Response:
        mer = get_object_or_404(Merchant, pk=merchant_id)
        body = MerchantUpdateSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        changes: dict[str, dict[str, str]] = {}

        # Merchant-owned fields.
        merchant_fields = []
        for field in ("name", "legal_name"):
            if field in data and getattr(mer, field) != data[field]:
                changes[field] = {"before": getattr(mer, field), "after": data[field]}
                setattr(mer, field, data[field])
                merchant_fields.append(field)
        if merchant_fields:
            mer.save(update_fields=merchant_fields)

        # Contact pair lives on the MerchantSettings sidecar (created on demand).
        contact = {k: data[k] for k in ("contact_email", "contact_phone") if k in data}
        if contact:
            settings, _ = MerchantSettings.objects.get_or_create(merchant=mer)
            settings_fields = []
            for field, value in contact.items():
                if getattr(settings, field) != value:
                    changes[field] = {"before": getattr(settings, field), "after": value}
                    setattr(settings, field, value)
                    settings_fields.append(field)
            if settings_fields:
                settings.save(update_fields=settings_fields)

        if changes:
            audit.record(
                request,
                "merchant.update",
                target_type="merchant",
                target_id=str(mer.id),
                metadata={"changes": changes},
            )

        mer.refresh_from_db()
        return Response(MerchantDetailSerializer(self._detail_payload(mer)).data)

    @staticmethod
    def _detail_payload(mer: Merchant) -> dict:
        sub = subscription_for(mer)
        settings = getattr(mer, "settings", None)
        meta = getattr(mer, "admin_meta", None)

        return {
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
