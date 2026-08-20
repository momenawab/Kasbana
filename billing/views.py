"""Billing endpoints (contract §3.6 · Phase 1.7).

Read state (``GET /billing``), start a checkout (``POST /billing/subscribe`` →
gateway URL), list invoices, cancel, and the unauthenticated gateway webhook
(``/billing/webhook/paymob``) that drives the subscription state machine.

The gateway adapter (``billing.gateways``) is faked in tests and runs in stub
mode locally; real Paymob round-trips are a staging concern.
"""

from __future__ import annotations

import logging

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import coupons, services
from billing.gateways import DEFAULT_PROVIDER, get_gateway
from billing.gateways.base import WebhookVerificationError
from billing.models import Coupon, Invoice, Plan
from billing.plans import BillingInterval, BillingStatus, plan_price
from billing.serializers import (
    BillingStateSerializer,
    CancelRequestSerializer,
    CheckoutResponseSerializer,
    InvoiceSerializer,
    PlanOptionSerializer,
    SubscribeRequestSerializer,
)
from billing.services import subscription_for
from billing.wire import plan_key_to_wire, plan_to_wire
from common.errors import Conflict
from common.permissions import IsAdminOrAbove, IsOwner
from core.enums import PlanTier
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
            # The negotiated plan's human name ("Enterprise Gold") — §12.5. The
            # wire ``plan`` above is only the tier, so without this an
            # Enterprise merchant could not see *which* deal they are on. Blank
            # on a public tier, where the tier name says it all.
            "plan_name": sub.enterprise_plan.name if sub.enterprise_plan else "",
            "trial_ends_at": sub.trial_ends_at if sub.trial_active() else None,
            "price_egp": plan_price(plan, sub.billing_interval),
            "billing_interval": sub.billing_interval,
            "usage": entitlements.usage(merchant),
            "next_renewal": sub.current_period_end,
            "cancels_on": sub.cancels_on(),
            "payment_method": payment_method,
        }
        return Response(BillingStateSerializer(payload).data)


class PlanCatalogueView(APIView):
    """GET /billing/plans — the sellable tiers + their prices.

    Feeds the subscribe screen and the signup gate. Reads the same DB catalogue
    checkout prices from, so an admin's price edit shows up without a deploy.
    Any authenticated merchant user may read it: it is public pricing, and a
    merchant sitting at the signup gate has no plan yet.
    """

    permission_classes = [IsAdminOrAbove]
    serializer_class = PlanOptionSerializer

    @extend_schema(responses=PlanOptionSerializer(many=True))
    def get(self, request: Request) -> Response:
        rows = [
            {
                "key": plan_key_to_wire(p.key),
                "name": p.name,
                "price_egp": plan_price(p.key),
                "price_egp_annual": plan_price(p.key, BillingInterval.ANNUAL),
            }
            for p in Plan.objects.filter(is_public=True, archived=False)
        ]
        return Response(PlanOptionSerializer(rows, many=True).data)


class SubscribeView(APIView):
    """POST /billing/subscribe — create a gateway checkout for the chosen plan."""

    permission_classes = [IsOwner]
    serializer_class = SubscribeRequestSerializer

    @extend_schema(request=SubscribeRequestSerializer, responses=CheckoutResponseSerializer)
    def post(self, request: Request) -> Response:
        body = SubscribeRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        plan = body.validated_data["plan"]
        interval = body.validated_data["interval"]

        merchant = get_request_merchant(request)
        sub = subscription_for(merchant)

        # An Enterprise merchant pays for the plan an admin negotiated with
        # them, whatever the client asked for. The catalogue key is resolved
        # server-side from the assignment — the request body must never be able
        # to name a price, and their plan is not offered at self-serve anyway.
        negotiated = sub.enterprise_plan if sub.plan == PlanTier.ENTERPRISE else None
        if negotiated is not None:
            plan = negotiated.key
            interval = sub.pending_interval or sub.billing_interval

        if (
            sub.status == BillingStatus.ACTIVE
            and (negotiated.key if negotiated is not None else sub.plan) == plan
            and sub.billing_interval == interval
        ):
            # Same plan *and* interval — switching monthly<->annual on the plan
            # they already hold is a legitimate re-subscribe, not a duplicate.
            raise Conflict("Already subscribed to this plan.")

        # Optional discount code (Phase 11): validate + apply to the charge, and
        # record the (capped) redemption. Only percent/fixed change a checkout
        # charge; other coupon types are admin-granted, not used here.
        amount = plan_price(plan, interval)
        coupon_code = body.validated_data.get("coupon", "")
        applied_coupon = None
        if coupon_code:
            coupon = coupons.get_active(coupon_code)
            if coupon is None:
                raise DRFValidationError({"coupon": "Unknown code."})
            if coupon.type not in (Coupon.Type.PERCENT, Coupon.Type.FIXED):
                raise DRFValidationError({"coupon": "This code isn't a checkout discount."})
            try:
                coupons.validate(coupon, merchant, plan)
            except coupons.CouponError as exc:
                raise DRFValidationError({"coupon": exc.message}) from exc
            amount = coupons.discounted_amount(coupon, amount)
            applied_coupon = coupon

        provider = request.query_params.get("provider", DEFAULT_PROVIDER)
        try:
            gateway = get_gateway(provider)
        except ValueError as exc:
            # Unknown/unsupported provider — never route money there.
            raise DRFValidationError({"provider": "Unsupported payment provider."}) from exc
        session = gateway.create_checkout(
            merchant_id=str(merchant.id),
            plan=plan,
            amount_egp=amount,
            customer_email=getattr(getattr(request, "user", None), "email", ""),
            subscription_plan_id=self._paymob_plan_id(plan, interval),
        )
        services.begin_checkout(
            merchant,
            # ``pending_plan`` is a PlanTier column, so it records the *tier*;
            # for Enterprise the negotiated plan is already pinned by the
            # enterprise_plan FK, which activation preserves.
            plan=PlanTier.ENTERPRISE if negotiated is not None else plan,
            provider=provider,
            gateway_ref=session.gateway_ref,
            interval=interval,
        )
        if applied_coupon is not None:
            coupons.redeem(
                applied_coupon,
                merchant,
                discount_egp=plan_price(plan, interval) - amount,
                detail=f"{plan} {interval} checkout",
            )
        return Response({"checkout_url": session.checkout_url})

    def _paymob_plan_id(self, plan: str, interval: str) -> str:
        """The Paymob Subscription Plan this checkout should attach to.

        Blank means "charge once, do not set up recurring billing" — which is
        what happens until ops has run ``create_paymob_plans`` for this
        environment. Deliberately not an error: a merchant being charged once
        and needing a nudge to re-subscribe is recoverable, whereas refusing
        every checkout would take the product offline. The unmapped state is
        loud in the log instead.
        """
        row = Plan.objects.filter(key=plan).first()
        paymob_plan_id = row.paymob_plan_id(interval) if row is not None else ""
        if not paymob_plan_id:
            logger.error(
                "no Paymob plan id for %s/%s — checkout will be a ONE-TIME charge "
                "with no recurring subscription. Run `manage.py create_paymob_plans`.",
                plan,
                interval,
            )
        return paymob_plan_id


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
        sub = services.schedule_cancel(merchant)
        logger.info(
            "Subscription cancel requested for %s (reason=%s, effective=%s)",
            merchant.id,
            body.validated_data.get("reason", ""),
            sub.cancels_on() or "immediately",
        )
        return Response({"ok": True, "cancels_on": sub.cancels_on()})


class _WebhookView(APIView):
    """Base for the unauthenticated gateway webhooks (security:[] in contract)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "webhook"  # per-IP cap on the unauthenticated webhooks (Phase 1.8)
    provider: str = ""

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        from billing import webhook_log
        from billing.models import WebhookDelivery

        try:
            gateway = get_gateway(self.provider)
        except ValueError:
            # Defensive: an unknown/unconfigured provider on the webhook path is
            # acknowledged inertly rather than 500ing.
            logger.info("%s webhook hit but provider is not enabled", self.provider)
            webhook_log.record(self.provider, WebhookDelivery.Status.DISABLED)
            return Response({"detail": "provider not enabled"}, status=status.HTTP_404_NOT_FOUND)
        try:
            event = gateway.verify_and_parse(headers=dict(request.headers), body=request.body)
        except WebhookVerificationError as exc:
            logger.warning("%s webhook verification failed: %s", self.provider, exc)
            webhook_log.record(self.provider, WebhookDelivery.Status.INVALID, error=str(exc))
            return Response({"detail": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        sub = services.apply_webhook_event(event)
        if sub is None:
            logger.warning("%s webhook: no merchant for ref=%s", self.provider, event.gateway_ref)
            webhook_log.record(self.provider, WebhookDelivery.Status.NO_MERCHANT, event=event)
        else:
            webhook_log.record(self.provider, WebhookDelivery.Status.PROCESSED, event=event)
        # Always 200 once verified so the gateway stops retrying (contract).
        return Response({"received": True, "at": timezone.now().isoformat()})


class PaymobWebhookView(_WebhookView):
    provider = "paymob"


class PaymobSubscriptionWebhookView(APIView):
    """POST /billing/webhook/paymob/subscription — recurring-subscription events.

    Registered as every Paymob Subscription Plan's ``webhook_url``. Separate
    from ``PaymobWebhookView`` because the payload shape and the HMAC scheme
    both differ, and because only these events move the billing period forward.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "webhook"
    provider = "paymob"

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        from billing import webhook_log
        from billing.models import WebhookDelivery

        gateway = get_gateway(self.provider)
        try:
            event = gateway.verify_and_parse_subscription_event(
                headers=dict(request.headers), body=request.body
            )
        except WebhookVerificationError as exc:
            logger.warning("paymob subscription webhook verification failed: %s", exc)
            webhook_log.record_subscription(
                self.provider, WebhookDelivery.Status.INVALID, error=str(exc)
            )
            return Response({"detail": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        sub = services.apply_subscription_event(event)
        if sub is None:
            # Nothing local matches this Paymob subscription — e.g. a plan
            # created against another environment pointing here. Ack anyway so
            # Paymob stops retrying, but keep the row so ops can see it.
            logger.warning(
                "paymob subscription webhook: no local subscription for id=%s (trigger=%s)",
                event.subscription_id,
                event.trigger_type,
            )
            webhook_log.record_subscription(
                self.provider, WebhookDelivery.Status.NO_MERCHANT, event=event
            )
        else:
            webhook_log.record_subscription(
                self.provider, WebhookDelivery.Status.PROCESSED, event=event
            )
        return Response({"received": True, "at": timezone.now().isoformat()})
