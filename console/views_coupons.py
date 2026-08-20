"""Coupon / promotion endpoints (Phase 11).

Discounts affect revenue → create/edit/apply are gated to **Finance/Super-admin**
(``IsFinanceAdmin``); list/detail/redemption-report are open to any admin.
Redemption caps are enforced server-side (``billing.coupons``); every mutation is
audited.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing import coupons as coupon_svc
from billing import services
from billing.coupons import normalize
from billing.models import Coupon, CouponGroup, CouponRedemption
from common.pagination import DefaultCursorPagination
from console import audit
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_coupons import (
    ApplyCouponSerializer,
    CouponCreateSerializer,
    CouponGroupSerializer,
    CouponGroupWriteSerializer,
    CouponRedemptionSerializer,
    CouponSerializer,
)
from core.models import Merchant


def _redemption_row(r: CouponRedemption) -> dict:
    return {
        "id": r.id,
        "merchant": {"id": r.merchant_id, "name": r.merchant.name, "slug": r.merchant.slug},
        "discount_egp": r.discount_egp,
        "detail": r.detail,
        "created_at": r.created_at,
    }


class CouponListView(AdminAPIView):
    """GET /coupons (any admin) · POST create (Finance+)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsFinanceAdmin]
        return [cls() for cls in classes]

    @extend_schema(responses=CouponSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = Coupon.objects.all()
        # Optional grouping filter: ?group=<uuid> narrows to a group; ?group=none
        # returns only ungrouped coupons. Absent = every coupon (today's default).
        group = request.query_params.get("group")
        if group == "none":
            qs = qs.filter(group__isnull=True)
        elif group:
            try:
                qs = qs.filter(group_id=UUID(group))
            except ValueError:
                qs = qs.none()  # malformed id → no matches, never a 500
        return Response(CouponSerializer(qs, many=True).data)

    @extend_schema(request=CouponCreateSerializer, responses=CouponSerializer)
    def post(self, request: Request) -> Response:
        body = CouponCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        coupon = body.save()
        audit.record(
            request,
            "coupon.create",
            target_type="coupon",
            target_id=str(coupon.id),
            metadata={"code": coupon.code, "type": coupon.type, "value": str(coupon.value)},
        )
        return Response(CouponSerializer(coupon).data, status=201)


class CouponDetailView(AdminAPIView):
    """GET /coupons/{code} (any admin) · PATCH (Finance+)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsFinanceAdmin]
        return [cls() for cls in classes]

    def _get(self, code: str) -> Coupon:
        return get_object_or_404(Coupon, code=normalize(code))

    @extend_schema(responses=CouponSerializer)
    def get(self, request: Request, code: str) -> Response:
        return Response(CouponSerializer(self._get(code)).data)

    @extend_schema(request=None, responses=CouponSerializer)
    def patch(self, request: Request, code: str) -> Response:
        from console.serializers_coupons import CouponUpdateSerializer

        coupon = self._get(code)
        before = CouponSerializer(coupon).data
        body = CouponUpdateSerializer(coupon, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save()
        audit.record(
            request,
            "coupon.update",
            target_type="coupon",
            target_id=str(coupon.id),
            metadata={
                "code": coupon.code,
                "before": before,
                "after": CouponSerializer(coupon).data,
            },
        )
        return Response(CouponSerializer(coupon).data)


class CouponRedemptionsView(AdminAPIView):
    """GET /coupons/{code}/redemptions — the redemption report (any admin)."""

    @extend_schema(responses=CouponRedemptionSerializer(many=True))
    def get(self, request: Request, code: str) -> Response:
        coupon = get_object_or_404(Coupon, code=normalize(code))
        rows = coupon.redemptions.select_related("merchant").all()
        return Response(
            CouponRedemptionSerializer([_redemption_row(r) for r in rows], many=True).data
        )


class ApplyCouponView(AdminAPIView):
    """POST /merchants/{id}/apply-coupon {code} — admin-grant a coupon directly.

    Supports the non-checkout types: ``trial_extension`` (extend the trial by
    ``value`` days) and ``free_months`` (grant comp / free access). Percent/fixed
    codes are consumed at checkout, not here. Finance+; audited.
    """

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=ApplyCouponSerializer, responses=None)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = ApplyCouponSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        coupon = coupon_svc.get_active(body.validated_data["code"])
        if coupon is None:
            return Response(
                {"error": {"code": "COUPON_NOT_FOUND", "message": "Unknown code."}}, status=404
            )
        if coupon.type not in (Coupon.Type.TRIAL_EXTENSION, Coupon.Type.FREE_MONTHS):
            return Response(
                {
                    "error": {
                        "code": "COUPON_NOT_GRANTABLE",
                        "message": "Percent/fixed codes are applied at checkout, not granted.",
                    }
                },
                status=400,
            )
        try:
            coupon_svc.validate(coupon, merchant)
        except coupon_svc.CouponError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=409)

        if coupon.type == Coupon.Type.TRIAL_EXTENSION:
            days = int(coupon.value)
            services.extend_trial(merchant, days)
            detail = f"trial +{days}d"
        else:  # FREE_MONTHS
            months = int(coupon.value)
            services.set_comp(merchant, True)
            detail = f"free {months}mo (comp)"

        coupon_svc.redeem(coupon, merchant, discount_egp=Decimal("0"), detail=detail)
        audit.record(
            request,
            "coupon.apply",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"code": coupon.code, "type": coupon.type, "detail": detail},
        )
        return Response({"ok": True, "detail": detail})


class CouponGroupListView(AdminAPIView):
    """GET /coupon-groups (any admin, paginated) · POST create (Finance+).

    Groups are a purely organisational wrapper over coupons (Phase 11 deferral):
    a coupon works identically whether grouped or not.
    """

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsFinanceAdmin]
        return [cls() for cls in classes]

    @extend_schema(responses=CouponGroupSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = CouponGroup.objects.annotate(coupon_count_annotated=Count("coupons"))
        paginator = DefaultCursorPagination()
        page = paginator.paginate_queryset(qs, request, view=self) or []
        return paginator.get_paginated_response(CouponGroupSerializer(page, many=True).data)

    @extend_schema(request=CouponGroupWriteSerializer, responses=CouponGroupSerializer)
    def post(self, request: Request) -> Response:
        body = CouponGroupWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        group = body.save()
        audit.record(
            request,
            "coupon_group.create",
            target_type="coupon_group",
            target_id=str(group.id),
            metadata={"name": group.name},
        )
        return Response(CouponGroupSerializer(group).data, status=201)


class CouponGroupDetailView(AdminAPIView):
    """GET /coupon-groups/{id} (any admin) · PATCH/DELETE (Finance+)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsFinanceAdmin]
        return [cls() for cls in classes]

    def _get(self, group_id: str) -> CouponGroup:
        return get_object_or_404(CouponGroup, pk=group_id)

    @extend_schema(responses=CouponGroupSerializer)
    def get(self, request: Request, group_id: str) -> Response:
        return Response(CouponGroupSerializer(self._get(group_id)).data)

    @extend_schema(request=CouponGroupWriteSerializer, responses=CouponGroupSerializer)
    def patch(self, request: Request, group_id: str) -> Response:
        group = self._get(group_id)
        before = CouponGroupSerializer(group).data
        body = CouponGroupWriteSerializer(group, data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        body.save()
        audit.record(
            request,
            "coupon_group.update",
            target_type="coupon_group",
            target_id=str(group.id),
            metadata={"before": before, "after": CouponGroupSerializer(group).data},
        )
        return Response(CouponGroupSerializer(group).data)

    @extend_schema(request=None, responses=None)
    def delete(self, request: Request, group_id: str) -> Response:
        group = self._get(group_id)
        name = group.name
        # SET_NULL: the group's coupons survive the delete, just become ungrouped.
        detached = group.coupons.count()
        group.delete()
        audit.record(
            request,
            "coupon_group.delete",
            target_type="coupon_group",
            target_id=str(group_id),
            metadata={"name": name, "coupons_detached": detached},
        )
        return Response(status=204)
