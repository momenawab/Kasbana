"""Wallet card-design endpoint (notes 2-4).

``GET/PATCH /cards/{id}/wallet-design`` — the merchant-editable Apple/Google pass
variables for one card. GET is open to any card manager (so the editor can show
current values, even locked); PATCH is gated by the ``custom_branding``
entitlement (free plans keep the smart defaults). Tenancy-scoped: a card from
another merchant is 404.
"""

from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import entitlements
from common.permissions import CanManageCards
from core.models import Card
from core.tenancy import get_scoped
from wallets import templates as templates_mod
from wallets.models import WalletCardDesign
from wallets.serializers import WalletCardDesignSerializer


class CardWalletDesignView(APIView):
    """GET/PATCH the wallet pass design for one card."""

    permission_classes = [CanManageCards]
    serializer_class = WalletCardDesignSerializer

    def _design(self, request: Request, card_id: str) -> WalletCardDesign:
        card = get_scoped(Card, request, pk=card_id)
        design, _ = WalletCardDesign.objects.get_or_create(
            card=card, defaults={"merchant": card.merchant}
        )
        return design

    @extend_schema(responses=WalletCardDesignSerializer)
    def get(self, request: Request, card_id: str) -> Response:
        design = self._design(request, card_id)
        return Response(WalletCardDesignSerializer(design).data)

    @extend_schema(request=WalletCardDesignSerializer, responses=WalletCardDesignSerializer)
    def patch(self, request: Request, card_id: str) -> Response:
        design = self._design(request, card_id)
        # Rich pass design is a paid feature; free plans keep the defaults.
        entitlements.enforce(design.merchant, "custom_branding")
        ser = WalletCardDesignSerializer(design, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class WalletTemplateListView(APIView):
    """``GET /wallet-templates`` — the layout-locked template catalog.

    One source of truth for the backend renderers and the frontend gallery: the
    fixed per-platform layouts live in code (``wallets.templates``); this exposes
    the compact, frontend-safe list plus the platform-logo URL (so the preview
    can render the real bottom-left logo when configured).
    """

    permission_classes: list[type[BasePermission]] = [CanManageCards]

    @extend_schema(tags=["wallets"])
    def get(self, request: Request) -> Response:
        return Response(
            {
                "templates": templates_mod.template_choices(),
                "platform_logo_url": getattr(settings, "WALLET_PLATFORM_LOGO_URL", ""),
            }
        )
