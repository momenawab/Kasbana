"""Compliance tools (Phase 13, PDPL): data export, right-to-be-forgotten,
consent records, and the data-retention policy.

Delete and export are the sharpest tools in the console — a delete is
irreversible and an export dumps a merchant's full PII bundle — so both are
gated to ``COMPLIANCE_DELETE`` / ``COMPLIANCE_EXPORT``, which only super-admin
holds (see ``console.rbac``). Consent records and *reading* the retention policy
are reads, open to any admin per convention; only *editing* retention is gated.
Every export and delete is audited.
"""

from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit, compliance
from console.models import AdminUser, RetentionPolicy
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_compliance import (
    ConsentRecordSerializer,
    MerchantDeleteConfirmSerializer,
    RetentionPolicySerializer,
)
from core.models import CustomerCard, Merchant


class MerchantDataExportView(AdminAPIView):
    """GET /merchants/{id}/export — the merchant's full data bundle as JSON
    (super-admin only; PII; audited)."""

    permission_classes = [IsAdminUser, require(Permission.COMPLIANCE_EXPORT)]

    @extend_schema(responses={(200, "application/json"): dict})
    def get(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        bundle = compliance.export_bundle(merchant)
        audit.record(
            request,
            "merchant.data_export",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"slug": merchant.slug},
        )
        response = Response(bundle)
        response["Content-Disposition"] = f'attachment; filename="merchant_{merchant.slug}.json"'
        return response


class MerchantDeleteView(AdminAPIView):
    """DELETE /merchants/{id} — right-to-be-forgotten: erase the merchant and
    everything that cascades off it (super-admin only; typed confirm; audited).
    """

    permission_classes = [IsAdminUser, require(Permission.COMPLIANCE_DELETE)]

    @extend_schema(request=MerchantDeleteConfirmSerializer, responses={204: None})
    def delete(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = MerchantDeleteConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        # Typed confirmation: the operator must type the exact slug. This makes
        # an irreversible cross-cascade delete impossible to trigger by accident.
        if body.validated_data["confirm"] != merchant.slug:
            return Response(
                {
                    "error": {
                        "code": "CONFIRM_MISMATCH",
                        "message": "Type the merchant's exact slug to confirm deletion.",
                    }
                },
                status=409,
            )

        # Snapshot BEFORE the cascade — afterwards there's nothing left to describe.
        snapshot = compliance.delete_snapshot(merchant)
        with transaction.atomic():
            audit.record(
                request,
                "merchant.delete",
                target_type="merchant",
                target_id=str(merchant.id),
                metadata={"reason": body.validated_data["reason"], **snapshot},
            )
            merchant.delete()
        return Response(status=204)


class MerchantConsentView(AdminAPIView):
    """GET /merchants/{id}/consent — the merchant's customers' PDPL consent
    records (any admin; read)."""

    @extend_schema(responses=ConsentRecordSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        cards = CustomerCard.objects.filter(merchant=merchant).order_by("-enrolled_at")
        return Response(ConsentRecordSerializer(cards, many=True).data)


class RetentionPolicyView(AdminAPIView):
    """GET /compliance/retention — the global policy (any admin).
    PATCH — edit it (``RETENTION_MANAGE``; super-admin only; audited)."""

    def get_permissions(self):  # type: ignore[no-untyped-def]
        if self.request.method == "PATCH":
            return [IsAdminUser(), require(Permission.RETENTION_MANAGE)()]
        return [IsAdminUser()]

    @extend_schema(responses=RetentionPolicySerializer)
    def get(self, request: Request) -> Response:
        return Response(RetentionPolicySerializer(RetentionPolicy.current()).data)

    @extend_schema(request=RetentionPolicySerializer, responses=RetentionPolicySerializer)
    def patch(self, request: Request) -> Response:
        policy = RetentionPolicy.current()
        before = RetentionPolicySerializer(policy).data
        serializer = RetentionPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        actor = request.user if isinstance(request.user, AdminUser) else None
        # updated_at is auto_now, so it refreshes on save without being passed.
        serializer.save(updated_by=actor, updated_by_email=getattr(actor, "email", ""))
        audit.record(
            request,
            "retention.update",
            target_type="retention_policy",
            target_id=str(policy.id),
            metadata={"before": before, "after": serializer.data},
        )
        return Response(serializer.data)
