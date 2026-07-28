"""Test-card endpoints — build a prospect's branded wallet pass for a proposal.

``GET  /demo-cards``            — every test card built so far.
``POST /demo-cards``            — create one (demo merchant + card + holder) and
                                  return its Apple/Google add-to-wallet URLs.
``GET  /demo-cards/{id}/pass``  — re-fetch those URLs for an existing card.
``DELETE /demo-cards/{id}``     — clean one up.

Gated on ``DEMO_CARDS_MANAGE`` (super-admin + Sales) and audited: the tool writes
real rows, even if they are demo ones.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from console import audit, demo_cards
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_demo_cards import (
    DemoCardCreateSerializer,
    DemoCardPassSerializer,
    DemoCardSerializer,
)
from core.models import Card


class DemoCardListView(AdminAPIView):
    """GET/POST /demo-cards — list or build a prospect test card."""

    permission_classes = [IsAdminUser, require(Permission.DEMO_CARDS_MANAGE)]

    @extend_schema(responses=DemoCardSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(DemoCardSerializer(demo_cards.demo_card_rows(), many=True).data)

    @extend_schema(request=DemoCardCreateSerializer, responses=DemoCardSerializer)
    def post(self, request: Request) -> Response:
        body = DemoCardCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        merchant_name = data.pop("merchant_name")

        result = demo_cards.create_demo_card(merchant_name=merchant_name, card_fields=data)
        audit.record(
            request,
            "demo_card.create",
            target_type="merchant",
            target_id=str(result["merchant_id"]),
            metadata={"merchant_name": merchant_name, "card_name": result["card_name"]},
        )
        return Response(DemoCardSerializer(result).data, status=201)


class DemoCardPassView(AdminAPIView):
    """GET /demo-cards/{card_id}/pass — add-to-wallet URLs for an existing card."""

    permission_classes = [IsAdminUser, require(Permission.DEMO_CARDS_MANAGE)]

    @extend_schema(responses=DemoCardPassSerializer)
    def get(self, request: Request, card_id: str) -> Response:
        card = get_object_or_404(Card, pk=card_id, merchant__is_demo=True)
        return Response(DemoCardPassSerializer(demo_cards.pass_urls(card)).data)


class DemoCardDetailView(AdminAPIView):
    """DELETE /demo-cards/{card_id} — remove a test card and its demo merchant."""

    permission_classes = [IsAdminUser, require(Permission.DEMO_CARDS_MANAGE)]

    @extend_schema(responses=None)
    def delete(self, request: Request, card_id: str) -> Response:
        card = get_object_or_404(Card, pk=card_id, merchant__is_demo=True)
        name = card.merchant.name
        demo_cards.delete_demo_card(card)
        audit.record(
            request,
            "demo_card.delete",
            target_type="merchant",
            target_id=str(card_id),
            metadata={"merchant_name": name},
        )
        return Response(status=204)
