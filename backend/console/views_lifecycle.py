"""Lifecycle, moderation & suspension endpoints (Phase 9).

- Lifecycle pipeline board + at-risk list — read-only, any admin.
- Suspend / unsuspend a merchant — **Super-admin only**, reason required,
  audited; suspension is enforced on the merchant API (``common.permissions``).
- Moderation queue: list flags (any admin), run the heuristic scan + resolve a
  flag (**Support+**), audited.
"""

from __future__ import annotations

from typing import cast

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit, lifecycle, moderation
from console.models import AdminUser, ContentFlag
from console.permissions import AdminAPIView, IsAdminUser, IsSuperAdmin, IsSupportAdmin
from console.serializers_lifecycle import (
    AtRiskSerializer,
    ContentFlagSerializer,
    PipelineSerializer,
    ResolveFlagSerializer,
    ScanResultSerializer,
    SuspendSerializer,
)
from core.enums import MerchantStatus
from core.models import Merchant


class PipelineView(AdminAPIView):
    """GET /lifecycle/pipeline — merchants bucketed by stage (any admin)."""

    @extend_schema(responses=PipelineSerializer)
    def get(self, request: Request) -> Response:
        return Response(PipelineSerializer(lifecycle.pipeline()).data)


class AtRiskView(AdminAPIView):
    """GET /lifecycle/at-risk — at-risk merchants with reasons (any admin)."""

    @extend_schema(responses=AtRiskSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(AtRiskSerializer(lifecycle.at_risk(), many=True).data)


class SuspendView(AdminAPIView):
    """POST /merchants/{id}/suspend {reason} — Super-admin only."""

    permission_classes = [IsAdminUser, IsSuperAdmin]

    @extend_schema(request=SuspendSerializer, responses=SuspendSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = SuspendSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        before = merchant.status
        merchant.status = MerchantStatus.SUSPENDED
        merchant.save(update_fields=["status"])
        audit.record(
            request,
            "merchant.suspend",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"reason": body.validated_data["reason"], "before": before},
        )
        return Response({"reason": body.validated_data["reason"]})


class UnsuspendView(AdminAPIView):
    """POST /merchants/{id}/unsuspend {reason} — Super-admin only."""

    permission_classes = [IsAdminUser, IsSuperAdmin]

    @extend_schema(request=SuspendSerializer, responses=SuspendSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = SuspendSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        before = merchant.status
        merchant.status = MerchantStatus.ACTIVE
        merchant.save(update_fields=["status"])
        audit.record(
            request,
            "merchant.unsuspend",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"reason": body.validated_data["reason"], "before": before},
        )
        return Response({"reason": body.validated_data["reason"]})


class ModerationQueueView(AdminAPIView):
    """GET /moderation/flags?status=pending — the review queue (any admin)."""

    @extend_schema(
        parameters=[OpenApiParameter("status", str, description="pending|approved|rejected")],
        responses=ContentFlagSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        status = (request.query_params.get("status") or "pending").strip()
        qs = ContentFlag.objects.select_related("merchant").filter(status=status)
        return Response(ContentFlagSerializer([moderation.flag_row(f) for f in qs], many=True).data)


class ModerationScanView(AdminAPIView):
    """POST /moderation/scan — run the heuristic content scan (Support+)."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=None, responses=ScanResultSerializer)
    def post(self, request: Request) -> Response:
        result = moderation.run_scan()
        audit.record(request, "moderation.scan", target_type="platform", metadata=result)
        return Response(result)


class ResolveFlagView(AdminAPIView):
    """POST /moderation/flags/{id}/resolve {action, notes} — Support+."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=ResolveFlagSerializer, responses=ContentFlagSerializer)
    def post(self, request: Request, flag_id: str) -> Response:
        flag = get_object_or_404(ContentFlag, pk=flag_id)
        body = ResolveFlagSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        action = body.validated_data["action"]

        if flag.status != ContentFlag.Status.PENDING:
            return Response(
                {
                    "error": {
                        "code": "FLAG_ALREADY_RESOLVED",
                        "message": "This flag has already been reviewed.",
                    }
                },
                status=409,
            )

        flag.status = (
            ContentFlag.Status.APPROVED if action == "approve" else ContentFlag.Status.REJECTED
        )
        flag.resolution_notes = body.validated_data.get("notes", "")
        flag.resolved_by = cast(AdminUser, request.user)
        flag.resolved_at = timezone.now()
        flag.save(update_fields=["status", "resolution_notes", "resolved_by", "resolved_at"])
        audit.record(
            request,
            "moderation.resolve",
            target_type="content_flag",
            target_id=str(flag.id),
            metadata={
                "action": action,
                "target_type": flag.target_type,
                "target_id": flag.target_id,
                "merchant_id": str(flag.merchant_id),
                "notes": flag.resolution_notes,
            },
        )
        return Response(ContentFlagSerializer(moderation.flag_row(flag)).data)
