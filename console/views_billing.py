"""Dunning + reconciliation endpoints (Phase 5)."""

from __future__ import annotations

from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit
from console import billing as billing_queries
from console.merchants import owner_contact
from console.permissions import AdminAPIView, IsAdminUser, IsFinanceAdmin
from console.serializers_billing import (
    DunningRowSerializer,
    NotifyRequestSerializer,
    NotifyResponseSerializer,
    ReconciliationSerializer,
)
from core.models import Merchant


class DunningListView(AdminAPIView):
    """GET /billing/dunning — merchants whose subscription is PAST_DUE."""

    @extend_schema(responses=DunningRowSerializer(many=True))
    def get(self, request: Request) -> Response:
        rows = [billing_queries.dunning_row(s) for s in billing_queries.dunning_queryset()]
        return Response(DunningRowSerializer(rows, many=True).data)


class DunningNotifyView(AdminAPIView):
    """POST /merchants/{id}/dunning/notify — email the owner a payment reminder."""

    permission_classes = [IsAdminUser, IsFinanceAdmin]

    @extend_schema(request=NotifyRequestSerializer, responses=NotifyResponseSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = NotifyRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        owner = owner_contact(merchant)
        sent = False
        if owner["email"]:
            send_mail(
                subject="Action needed: your Stampn subscription payment",
                message=(
                    f"Hi {owner['name'] or ''},\n\n"
                    f"There's an outstanding payment issue on your {merchant.name} "
                    "subscription. Please complete checkout from the Billing page in "
                    "your Stampn dashboard, or contact us, to keep your subscription "
                    "active.\n\n"
                    "— Stampn"
                ),
                from_email=None,
                recipient_list=[owner["email"]],
                fail_silently=True,
            )
            sent = True

        audit.record(
            request,
            "dunning.notify",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"sent": sent, "reason": body.validated_data.get("reason", "")},
        )
        return Response({"sent": sent})


class ReconciliationView(AdminAPIView):
    """GET /billing/reconciliation — internal invoice/subscription consistency report."""

    @extend_schema(responses=ReconciliationSerializer)
    def get(self, request: Request) -> Response:
        return Response(ReconciliationSerializer(billing_queries.reconciliation_report()).data)
