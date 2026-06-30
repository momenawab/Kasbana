"""Loyalty engine endpoints (contract §3.6 · Phase 2 · staff-auth).

Thin API layer over ``core.ledger`` — the single mutation chokepoint that owns
balance math and anti-fraud (cooldown, daily/per-staff caps). These views never
write to ``StampLedger`` or ``CustomerCard.stamp_count`` directly (contract §1).

Flow (contract §5): resolve the caller's ``CustomerCard`` *within their merchant*
(``get_scoped`` → cross-tenant IDs are 404), mutate via ``ledger``, then ask the
wallet façade to push a live pass update. ``loyalty/`` calls only
``wallets.service`` — never the Apple/Google backends directly.

Judgment calls where the contract is silent (Phase 2):
- min role = Scanner+ on all three endpoints (a counter cashier stamps/redeems);
- stamp/redeem return 200 (actions, not resource creation like enroll's 201);
- redeem validates ``reward`` belongs to the card's own program (§ RedeemView).
"""

from __future__ import annotations

from typing import cast

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.middleware import resolve_staff
from common.permissions import IsScannerOrAbove
from core import ledger
from core.models import CustomerCard, Reward, StaffUser
from core.tenancy import get_scoped
from loyalty.serializers import (
    CardStateSerializer,
    RedeemRequestSerializer,
    RedeemResponseSerializer,
    ScanRequestSerializer,
    StampRequestSerializer,
    StampResponseSerializer,
)
from wallets import service as wallet


def _card_state(card: CustomerCard) -> dict:
    """Shared ``CardState`` payload for the scan + card-state endpoints.

    Surfaces the program's active reward (lowest threshold first) so the cashier
    UI can redeem in one tap; ``None``/blank when no active reward is configured.
    """
    reward = card.card.rewards.filter(is_active=True).order_by("threshold").first()
    return CardStateSerializer(
        {
            "customer_card_id": card.id,
            "customer_name": card.customer_name,
            "stamp_count": card.stamp_count,
            "stamps_required": card.card.stamps_required,
            "reward_ready": ledger.is_reward_ready(card),
            "status": card.status,
            "reward_id": reward.id if reward else None,
            "reward_title": reward.title if reward else "",
        }
    ).data


class StampView(APIView):
    """POST /loyalty/stamp — add a stamp and push a live pass update."""

    permission_classes = [IsScannerOrAbove]

    @extend_schema(request=StampRequestSerializer, responses=StampResponseSerializer)
    def post(self, request: Request) -> Response:
        body = StampRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        card = get_scoped(CustomerCard, request, id=body.validated_data["customer_card_id"])
        # Resolved + cached by IsScannerOrAbove; non-null here (bound to merchant).
        staff = cast("StaffUser | None", resolve_staff(request))

        # Anti-fraud + balance update happen inside the ledger; it may raise
        # CooldownActive (429) / RateLimited (429), rendered via the envelope.
        ledger.add_stamp(
            card,
            staff=staff,
            location=getattr(staff, "location", None),
            delta=body.validated_data["delta"],
        )
        # The ledger mutates a row-locked re-fetch, so refresh our instance.
        card.refresh_from_db(fields=["stamp_count", "last_event_at"])

        # Engage automation (Phase 1.7): fire the reward-ready trigger inline
        # the moment a stamp tips the card to its threshold. Best-effort — a
        # disabled automation / missing capability / quota simply no-ops.
        if ledger.is_reward_ready(card):
            from messaging.tasks import fire_for_customer

            fire_for_customer(card.merchant, card, "reward_ready")

        # Enqueues wallets.tasks.push_pass_update. Tests verify this is *called*;
        # that the pass visibly updates on a real device needs Redis + a Celery
        # worker + live Apple/Google creds, i.e. Momen's integration smoke test
        # (not closable from inside this phase). Returns 500 if the broker is down.
        wallet.push_update(card)

        payload = StampResponseSerializer(
            {
                "customer_card_id": card.id,
                "stamp_count": card.stamp_count,
                "stamps_required": card.card.stamps_required,
                "reward_ready": ledger.is_reward_ready(card),
            }
        ).data
        return Response(payload)


class RedeemView(APIView):
    """POST /loyalty/redeem — claim a reward, decrementing the balance."""

    permission_classes = [IsScannerOrAbove]

    @extend_schema(request=RedeemRequestSerializer, responses=RedeemResponseSerializer)
    def post(self, request: Request) -> Response:
        body = RedeemRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        card = get_scoped(CustomerCard, request, id=body.validated_data["customer_card_id"])
        staff = cast("StaffUser | None", resolve_staff(request))

        # The reward must belong to this card's own program (and be active) — a
        # reward from another program is indistinguishable from missing (404).
        reward = get_object_or_404(
            Reward, id=body.validated_data["reward_id"], card=card.card, is_active=True
        )

        # Raises RewardNotReady (422) when the balance is below the threshold.
        redemption = ledger.redeem_reward(
            card, reward, staff=staff, location=getattr(staff, "location", None)
        )
        card.refresh_from_db(fields=["stamp_count", "last_event_at"])

        # Verified as *enqueued*, not executed against real wallets — see StampView.
        wallet.push_update(card)

        payload = RedeemResponseSerializer(
            {
                "redemption_id": redemption.id,
                "status": redemption.status,
                "stamp_count": card.stamp_count,
            }
        ).data
        return Response(payload)


class ScanView(APIView):
    """POST /loyalty/scan — resolve a scanned wallet QR to its card state.

    The cashier UI scans the customer's pass barcode and POSTs the raw ``code``;
    we strip the ``PASS_BARCODE_PREFIX``, resolve the card *within the caller's
    merchant* (cross-tenant codes are 404), and return the same ``CardState`` as
    ``GET /loyalty/cards/{id}`` — so the till can show "Ahmed — 7/10, reward
    ready" before the staffer taps stamp or redeem. Read-only; no ledger write.
    """

    permission_classes = [IsScannerOrAbove]

    @extend_schema(request=ScanRequestSerializer, responses=CardStateSerializer)
    def post(self, request: Request) -> Response:
        body = ScanRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        card = get_scoped(CustomerCard, request, id=body.validated_data["code"])
        return Response(_card_state(card))


class CardStateView(APIView):
    """GET /loyalty/cards/{customer_card_id} — current balance & reward state."""

    permission_classes = [IsScannerOrAbove]

    @extend_schema(responses=CardStateSerializer)
    def get(self, request: Request, customer_card_id: str) -> Response:
        card = get_scoped(CustomerCard, request, id=customer_card_id)
        return Response(_card_state(card))
