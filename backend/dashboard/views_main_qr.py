"""The merchant's main QR — one printed code, re-pointable at any program.

``GET  /settings/main-qr``        — the link, its assets, and the elected card.
``PATCH /settings/main-qr``       — elect a different card (no reprint needed).
``POST /settings/main-qr/rotate`` — mint a new token (invalidates the poster).

The token itself lives on ``enrollment.MerchantEnrollLink`` and is resolved for
the public join flow by ``enrollment.tokens.resolve_join_target``.
"""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import CanManageCards
from core.enums import CardStatus
from core.models import Card
from core.tenancy import get_request_merchant, get_scoped
from dashboard.qr_assets import build_qr_assets
from enrollment.tokens import get_or_issue_merchant_link, rotate_merchant_link


class MainQrCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class MainQrSerializer(serializers.Serializer):
    """GET/PATCH/POST /settings/main-qr response."""

    token = serializers.CharField()
    join_url = serializers.URLField()
    qr_svg = serializers.CharField(allow_blank=True)
    poster_pdf_url = serializers.CharField(allow_blank=True)
    primary_card = MainQrCardSerializer(allow_null=True)


class MainQrUpdateSerializer(serializers.Serializer):
    """PATCH body. ``null`` un-elects, leaving the main QR dormant (404s)."""

    primary_card_id = serializers.UUIDField(allow_null=True)


def _payload(request: Request, link: object) -> dict:
    """Build the response for a link, rendering QR assets only when a card is
    elected — there is nothing to render a poster *for* otherwise."""
    merchant = get_request_merchant(request)
    join_url = f"{settings.ENROLL_BASE_URL}/enroll/{link.token}"  # type: ignore[attr-defined]
    card = link.primary_card  # type: ignore[attr-defined]

    data: dict = {
        "token": link.token,  # type: ignore[attr-defined]
        "join_url": join_url,
        "qr_svg": "",
        "poster_pdf_url": "",
        "primary_card": {"id": card.id, "name": card.name} if card else None,
    }
    if card is not None:
        # Namespace the poster by merchant: this renders the *same* card at a
        # different join URL than /cards/{id}/qr, so a shared key would make each
        # poster's prune sweep delete the other's file on every request.
        data.update(
            build_qr_assets(request, merchant, card, join_url, poster_key=f"main_{merchant.id}")
        )
    return data


class MainQrView(APIView):
    """GET + PATCH /settings/main-qr."""

    permission_classes = [CanManageCards]
    serializer_class = MainQrSerializer

    @extend_schema(responses=MainQrSerializer)
    def get(self, request: Request) -> Response:
        link = get_or_issue_merchant_link(get_request_merchant(request))
        return Response(MainQrSerializer(_payload(request, link)).data)

    @extend_schema(request=MainQrUpdateSerializer, responses=MainQrSerializer)
    def patch(self, request: Request) -> Response:
        body = MainQrUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        card_id = body.validated_data["primary_card_id"]

        card = None
        if card_id is not None:
            # get_scoped 404s a foreign card, so a cross-tenant id is
            # indistinguishable from a missing one.
            card = get_scoped(Card, request, pk=card_id)
            if card.status != CardStatus.ACTIVE:
                raise serializers.ValidationError(
                    {"primary_card_id": "Only an active card can be the main card."}
                )

        link = get_or_issue_merchant_link(get_request_merchant(request))
        link.primary_card = card
        link.save(update_fields=["primary_card", "updated_at"])
        return Response(MainQrSerializer(_payload(request, link)).data)


class MainQrRotateView(APIView):
    """POST /settings/main-qr/rotate — new token; every printed poster dies."""

    permission_classes = [CanManageCards]
    serializer_class = MainQrSerializer

    @extend_schema(request=None, responses=MainQrSerializer)
    def post(self, request: Request) -> Response:
        link = rotate_merchant_link(get_request_merchant(request))
        return Response(MainQrSerializer(_payload(request, link)).data)
