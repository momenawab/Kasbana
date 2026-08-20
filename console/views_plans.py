"""Plan catalogue endpoints (Phase 3).

``GET /api/admin/v1/plans`` — list (any admin). ``POST`` — create a plan.
``GET /plans/{key}`` — detail. ``PATCH`` — edit limits/features/price, or
archive it (``{"archived": true}`` — kept, not deleted, for historical
subscriptions). Mutations are gated to Super-admin/Finance and audited with
before/after; ``billing.entitlements`` picks up edits on next read via
``invalidate_plan_cache``.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from billing.models import Plan
from billing.plans import invalidate_plan_cache
from console import audit
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_plans import PlanSerializer, PlanUpdateSerializer


class PlanListView(AdminAPIView):
    """GET /plans — the catalogue. POST /plans — create (Finance/Super-admin)."""

    def get_permissions(self):
        classes = [IsAdminUser, IsFinanceAdmin] if self.request.method == "POST" else [IsAdminUser]
        return [cls() for cls in classes]

    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request: Request) -> Response:
        qs = Plan.objects.all()
        if request.query_params.get("include_archived") != "true":
            qs = qs.filter(archived=False)
        return Response(PlanSerializer(qs, many=True).data)

    @extend_schema(request=PlanSerializer, responses=PlanSerializer)
    def post(self, request: Request) -> Response:
        serializer = PlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        invalidate_plan_cache()
        audit.record(
            request,
            "plan.create",
            target_type="plan",
            target_id=plan.key,
            metadata={"after": PlanSerializer(plan).data},
        )
        return Response(PlanSerializer(plan).data, status=201)


class PlanDetailView(AdminAPIView):
    """GET /plans/{key} — detail. PATCH — edit or archive (Finance/Super-admin)."""

    def get_permissions(self):
        classes = [IsAdminUser, IsFinanceAdmin] if self.request.method == "PATCH" else [IsAdminUser]
        return [cls() for cls in classes]

    @extend_schema(responses=PlanSerializer)
    def get(self, request: Request, key: str) -> Response:
        plan = get_object_or_404(Plan, key=key)
        return Response(PlanSerializer(plan).data)

    @extend_schema(request=PlanUpdateSerializer, responses=PlanSerializer)
    def patch(self, request: Request, key: str) -> Response:
        plan = get_object_or_404(Plan, key=key)
        before = PlanSerializer(plan).data
        serializer = PlanUpdateSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_plan_cache()
        after = PlanSerializer(plan).data
        action = "plan.archive" if not before["archived"] and after["archived"] else "plan.update"
        audit.record(
            request,
            action,
            target_type="plan",
            target_id=plan.key,
            metadata={"before": before, "after": after},
        )
        return Response(after)
