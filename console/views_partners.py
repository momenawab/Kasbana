"""Partner / referral-program admin endpoints (Phase E.1).

Partners + the reward config affect comp (revenue), so every mutation is gated to
``PARTNERS_MANAGE`` (Finance/Super-admin) and audited; reads are open to any
admin. Attribution/reward *firing* lives in ``partners.services`` — these views
are the admin CRUD + reward report + manual attribution.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from common.pagination import DefaultCursorPagination
from console import audit
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_partners import (
    AssignReferralSerializer,
    PartnerCreateSerializer,
    PartnerProgramConfigSerializer,
    PartnerReferralSerializer,
    PartnerSerializer,
    PartnerUpdateSerializer,
)
from core.models import Merchant
from partners import services
from partners.models import Partner

CanManagePartners = require(Permission.PARTNERS_MANAGE)


def _with_counts(qs):
    return qs.select_related("merchant").annotate(
        referral_count_annotated=Count("referrals", distinct=True),
        converted_count_annotated=Count(
            "referrals", filter=Q(referrals__reward_granted=True), distinct=True
        ),
    )


class PartnerListView(AdminAPIView):
    """GET /partners (any admin, paginated) · POST create (Finance+)."""

    def get_permissions(self):
        classes = (
            [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, CanManagePartners]
        )
        return [cls() for cls in classes]

    @extend_schema(responses=PartnerSerializer(many=True))
    def get(self, request: Request) -> Response:
        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(_with_counts(Partner.objects.all()), request, view=self)
        return paginator.get_paginated_response(PartnerSerializer(page or [], many=True).data)

    @extend_schema(request=PartnerCreateSerializer, responses=PartnerSerializer)
    def post(self, request: Request) -> Response:
        body = PartnerCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        partner = body.save()
        audit.record(
            request,
            "partner.create",
            target_type="partner",
            target_id=str(partner.id),
            metadata={"code": partner.code, "merchant_id": str(partner.merchant_id)},
        )
        return Response(PartnerSerializer(partner).data, status=201)


class PartnerDetailView(AdminAPIView):
    """GET /partners/{id} (any admin) · PATCH/DELETE (Finance+)."""

    def get_permissions(self):
        classes = (
            [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, CanManagePartners]
        )
        return [cls() for cls in classes]

    def _get(self, partner_id: str) -> Partner:
        return get_object_or_404(_with_counts(Partner.objects.all()), pk=partner_id)

    @extend_schema(responses=PartnerSerializer)
    def get(self, request: Request, partner_id: str) -> Response:
        return Response(PartnerSerializer(self._get(partner_id)).data)

    @extend_schema(request=PartnerUpdateSerializer, responses=PartnerSerializer)
    def patch(self, request: Request, partner_id: str) -> Response:
        partner = get_object_or_404(Partner, pk=partner_id)
        before = PartnerSerializer(_with_counts(Partner.objects.filter(pk=partner.pk)).get()).data
        body = PartnerUpdateSerializer(partner, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save()
        after = PartnerSerializer(self._get(partner_id)).data
        audit.record(
            request,
            "partner.update",
            target_type="partner",
            target_id=str(partner.id),
            metadata={"before": before, "after": after},
        )
        return Response(after)

    @extend_schema(request=None, responses=None)
    def delete(self, request: Request, partner_id: str) -> Response:
        partner = get_object_or_404(Partner, pk=partner_id)
        code = partner.code
        partner.delete()
        audit.record(
            request,
            "partner.delete",
            target_type="partner",
            target_id=str(partner_id),
            metadata={"code": code},
        )
        return Response(status=204)


class PartnerReferralsView(AdminAPIView):
    """GET /partners/{id}/referrals — reward report · POST manual attribution."""

    def get_permissions(self):
        classes = (
            [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, CanManagePartners]
        )
        return [cls() for cls in classes]

    @extend_schema(responses=PartnerReferralSerializer(many=True))
    def get(self, request: Request, partner_id: str) -> Response:
        partner = get_object_or_404(Partner, pk=partner_id)
        rows = partner.referrals.select_related("referred_merchant").all()
        return Response(PartnerReferralSerializer(rows, many=True).data)

    @extend_schema(request=AssignReferralSerializer, responses=PartnerReferralSerializer)
    def post(self, request: Request, partner_id: str) -> Response:
        partner = get_object_or_404(Partner, pk=partner_id)
        body = AssignReferralSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        merchant = get_object_or_404(Merchant, pk=body.validated_data["merchant_id"])

        referral = services.assign_admin(partner, merchant)
        if referral is None:
            return Response(
                {
                    "error": {
                        "code": "ATTRIBUTION_CONFLICT",
                        "message": "Merchant is already referred, or is the partner itself.",
                    }
                },
                status=409,
            )
        audit.record(
            request,
            "partner.attribute",
            target_type="partner",
            target_id=str(partner.id),
            metadata={"referred_merchant_id": str(merchant.id)},
        )
        return Response(PartnerReferralSerializer(referral).data, status=201)


class PartnerConfigView(AdminAPIView):
    """GET /partner-config (any admin) · PATCH the global default (Finance+)."""

    def get_permissions(self):
        classes = (
            [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, CanManagePartners]
        )
        return [cls() for cls in classes]

    @extend_schema(responses=PartnerProgramConfigSerializer)
    def get(self, request: Request) -> Response:
        return Response(PartnerProgramConfigSerializer(services.program_config()).data)

    @extend_schema(request=PartnerProgramConfigSerializer, responses=PartnerProgramConfigSerializer)
    def patch(self, request: Request) -> Response:
        config = services.program_config()
        body = PartnerProgramConfigSerializer(config, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save()
        audit.record(
            request,
            "partner_config.update",
            target_type="partner_config",
            target_id=str(config.id),
            metadata=PartnerProgramConfigSerializer(config).data,
        )
        return Response(PartnerProgramConfigSerializer(config).data)
