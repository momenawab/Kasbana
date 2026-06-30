"""Billing endpoints (contract §3.6 · Phase 1.7).

Read state (``GET /billing``), start a checkout (``POST /billing/subscribe`` →
gateway URL), list invoices, cancel, and the unauthenticated gateway webhooks
(``/billing/webhook/{paymob,fawry}``) that drive the subscription state machine.

The gateway adapters (``billing.gateways``) are faked in tests and run in stub
mode locally; real Paymob/Fawry round-trips are a staging concern.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import services
from billing.gateways import DEFAULT_PROVIDER, get_gateway
from billing.gateways.base import WebhookVerificationError
from billing.models import Invoice
from billing.plans import PLAN_PRICES_EGP, BillingStatus
from billing.serializers import (
    BillingStateSerializer,
    CancelRequestSerializer,
    CheckoutResponseSerializer,
    InvoiceSerializer,
    SubscribeRequestSerializer,
)
from billing.services import subscription_for
from billing.wire import plan_to_wire
from common.errors import Conflict
from common.permissions import IsAdminOrAbove, IsOwner
from core.tenancy import get_request_merchant

logger = logging.getLogger(__name__)


class BillingStateView(APIView):
    """GET /billing — subscription state + usage + payment method."""

    permission_classes = [IsAdminOrAbove]
    serializer_class = BillingStateSerializer

    @extend_schema(responses=BillingStateSerializer)
    def get(self, request: Request) -> Response:
        from billing import entitlements

        merchant = get_request_merchant(request)
        sub = subscription_for(merchant)
        plan = sub.effective_plan() or sub.plan

        payment_method = None
        if sub.provider and sub.status == BillingStatus.ACTIVE:
            payment_method = {"brand": sub.provider, "last4": ""}

        payload = {
            "plan": plan_to_wire(sub),
            "trial_ends_at": sub.trial_ends_at if sub.trial_active() else None,
            "price_egp": PLAN_PRICES_EGP.get(plan, Decimal("0")),
            "usage": entitlements.usage(merchant),
            "next_renewal": sub.current_period_end,
            "payment_method": payment_method,
        }
        return Response(BillingStateSerializer(payload).data)


class SubscribeView(APIView):
    """POST /billing/subscribe — create a gateway checkout for the chosen plan."""

    permission_classes = [IsOwner]
    serializer_class = SubscribeRequestSerializer

    @extend_schema(request=SubscribeRequestSerializer, responses=CheckoutResponseSerializer)
    def post(self, request: Request) -> Response:
        body = SubscribeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        plan = body.validated_data["plan"]

        merchant = get_request_merchant(request)
        sub = subscription_for(merchant)
        if sub.status == BillingStatus.ACTIVE and sub.plan == plan:
            raise Conflict("Already subscribed to this plan.")

        provider = request.query_params.get("provider", DEFAULT_PROVIDER)
        try:
            gateway = get_gateway(provider)
        except ValueError as exc:
            # Unknown or disabled provider (e.g. Fawry) — never route money there.
            raise DRFValidationError({"provider": "Unsupported payment provider."}) from exc
        session = gateway.create_checkout(
            merchant_id=str(merchant.id),
            plan=plan,
            amount_egp=PLAN_PRICES_EGP.get(plan, Decimal("0")),
            customer_email=getattr(getattr(request, "user", None), "email", ""),
        )
        services.begin_checkout(
            merchant, plan=plan, provider=provider, gateway_ref=session.gateway_ref
        )
        return Response({"checkout_url": session.checkout_url})


class InvoiceListView(generics.ListAPIView):
    """GET /billing/invoices — paginated invoices (newest first)."""

    serializer_class = InvoiceSerializer
    permission_classes = [IsAdminOrAbove]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        return Invoice.objects.for_merchant(get_request_merchant(self.request))


class CancelView(APIView):
    """POST /billing/cancel — cancel the subscription (data retained)."""

    permission_classes = [IsOwner]
    serializer_class = CancelRequestSerializer

    @extend_schema(request=CancelRequestSerializer)
    def post(self, request: Request) -> Response:
        body = CancelRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        merchant = get_request_merchant(request)
        services.lock(merchant, status=BillingStatus.CANCELED)
        logger.info(
            "Subscription canceled for %s (reason=%s)",
            merchant.id,
            body.validated_data.get("reason", ""),
        )
        return Response({"ok": True})


class _WebhookView(APIView):
    """Base for the unauthenticated gateway webhooks (security:[] in contract)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    provider: str = ""

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        try:
            gateway = get_gateway(self.provider)
        except ValueError:
            # Provider implemented but disabled (e.g. Fawry). The route is kept
            # for the frozen contract, but we don't process its callbacks.
            logger.info("%s webhook hit but provider is disabled", self.provider)
            return Response({"detail": "provider not enabled"}, status=status.HTTP_404_NOT_FOUND)
        try:
            event = gateway.verify_and_parse(headers=dict(request.headers), body=request.body)
        except WebhookVerificationError as exc:
            logger.warning("%s webhook verification failed: %s", self.provider, exc)
            return Response({"detail": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        sub = services.apply_webhook_event(event)
        if sub is None:
            logger.warning("%s webhook: no merchant for ref=%s", self.provider, event.gateway_ref)
        # Always 200 once verified so the gateway stops retrying (contract).
        return Response({"received": True, "at": timezone.now().isoformat()})


class PaymobWebhookView(_WebhookView):
    provider = "paymob"


class FawryWebhookView(_WebhookView):
    provider = "fawry"
