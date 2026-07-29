"""Wallet Studio — author a merchant's pass design from the admin console.

``GET   /merchants/{id}/cards``                          — the merchant's cards.
``GET   /merchants/{id}/cards/{card_id}/wallet-design``  — design + raw overlays.
``PATCH /merchants/{id}/cards/{card_id}/wallet-design``  — save them.
``POST  /merchants/{id}/cards/{card_id}/pass-preview``   — dry-run, unsaved.
``POST  /merchants/{id}/cards/{card_id}/republish``      — push to live passes.

This is the same editor the merchant uses on their dashboard, plus the raw
pass-JSON overlay (see ``wallets.overlay``) that lets the platform build a card
far beyond what the template registry exposes.

Two deliberate differences from the merchant endpoint in ``wallets.views``:

* **No ``custom_branding`` entitlement gate.** The platform authoring a card for
  a merchant is not the merchant buying a feature; billing is orthogonal.
* **No template ``editable`` allowlist.** Authoring past the templates is the
  whole point of the studio.

Gated on ``WALLET_STUDIO_MANAGE``, which no role holds explicitly — super-admin
only, because a saved overlay re-renders passes already in customers' wallets.
Every mutation is audited.
"""

from __future__ import annotations

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from common import uploads
from console import audit
from console.permissions import AdminAPIView, IsAdminUser, require
from console.rbac import Permission
from console.serializers_wallet_studio import (
    MerchantCardRowSerializer,
    PassPreviewRequestSerializer,
    PassPreviewSerializer,
    RepublishResultSerializer,
)
from core.models import Card, CustomerCard, Merchant
from wallets import preview as preview_mod
from wallets.models import WalletCardDesign
from wallets.serializers import AdminWalletCardDesignSerializer
from wallets.views import WalletTemplateListSerializer

_STUDIO = [IsAdminUser, require(Permission.WALLET_STUDIO_MANAGE)]


def _card_for(merchant_id: str, card_id: str) -> Card:
    """The card, confirmed to belong to that merchant.

    The merchant id in the path is not decoration: without it a card id alone
    would let the studio edit any tenant's card from any merchant's page.
    """
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    return get_object_or_404(Card, pk=card_id, merchant=merchant)


def _design_for(card: Card) -> WalletCardDesign:
    design, _ = WalletCardDesign.objects.get_or_create(
        card=card, defaults={"merchant": card.merchant}
    )
    return design


class MerchantCardListView(AdminAPIView):
    """GET /merchants/{merchant_id}/cards — the studio's card rail."""

    permission_classes = _STUDIO

    @extend_schema(responses=MerchantCardRowSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        cards = (
            Card.objects.filter(merchant=merchant)
            .select_related("wallet_design")
            .annotate(customers_count=Count("customer_cards", distinct=True))
            .order_by("-created_at")
        )
        rows = [self._row(card) for card in cards]
        return Response(MerchantCardRowSerializer(rows, many=True).data)

    @staticmethod
    def _row(card: Card) -> dict:
        design = getattr(card, "wallet_design", None)
        return {
            "id": card.id,
            "name": card.name,
            "type": card.type,
            "status": card.status,
            "stamps_required": card.stamps_required,
            "reward_title": card.reward_title,
            "color_bg": card.color_bg,
            "color_fg": card.color_fg,
            "logo_url": card.logo_url,
            "template_key": design.template_key if design else "",
            "has_overlay": bool(design and (design.apple_overlay or design.google_overlay)),
            "customers_count": getattr(card, "customers_count", 0),
        }


class MerchantCardWalletDesignView(AdminAPIView):
    """GET/PATCH one card's wallet design + raw pass overlays."""

    permission_classes = _STUDIO
    serializer_class = AdminWalletCardDesignSerializer

    @extend_schema(responses=AdminWalletCardDesignSerializer)
    def get(self, request: Request, merchant_id: str, card_id: str) -> Response:
        design = _design_for(_card_for(merchant_id, card_id))
        return Response(AdminWalletCardDesignSerializer(design).data)

    @extend_schema(
        request=AdminWalletCardDesignSerializer, responses=AdminWalletCardDesignSerializer
    )
    def patch(self, request: Request, merchant_id: str, card_id: str) -> Response:
        card = _card_for(merchant_id, card_id)
        design = _design_for(card)
        ser = AdminWalletCardDesignSerializer(design, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()

        # The Google LoyaltyClass carries the program-level design, so it has to be
        # re-pushed for a class-side edit to appear. Per-customer objects are NOT
        # touched here — that is the explicit republish below, because a popular
        # card can hold tens of thousands of them.
        from wallets.tasks import sync_google_class

        sync_google_class.delay(str(card.id))

        audit.record(
            request,
            "wallet_studio.design.update",
            target_type="card",
            target_id=str(card.id),
            metadata={
                "merchant_id": str(card.merchant_id),
                "fields": sorted(ser.validated_data.keys()),
                "has_apple_overlay": bool(design.apple_overlay),
                "has_google_overlay": bool(design.google_overlay),
            },
        )
        return Response(ser.data)


class MerchantCardPassPreviewView(AdminAPIView):
    """POST /…/pass-preview — render the pass payloads without saving anything.

    The body may carry a candidate ``design``; it is validated and applied to an
    in-memory design row so the studio can show the result of an edit — and any
    validation error — before it is committed. Nothing is written either way.
    """

    permission_classes = _STUDIO

    @extend_schema(request=PassPreviewRequestSerializer, responses=PassPreviewSerializer)
    def post(self, request: Request, merchant_id: str, card_id: str) -> Response:
        card = _card_for(merchant_id, card_id)
        body = PassPreviewRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        design = _design_for(card)
        candidate = body.validated_data.get("design")
        if candidate:
            ser = AdminWalletCardDesignSerializer(design, data=candidate, partial=True)
            ser.is_valid(raise_exception=True)
            # Apply to the instance WITHOUT saving, then prime the card's related
            # cache so the pass builders read these unsaved values instead of
            # re-fetching the stored row.
            for field, value in ser.validated_data.items():
                setattr(design, field, value)
        card.wallet_design = design

        result = preview_mod.build_preview(card, body.validated_data.get("stamp_count"))
        return Response(PassPreviewSerializer(result).data)


class WalletStudioTemplateListView(AdminAPIView):
    """GET /wallet-studio/templates — the layout-locked template catalog.

    The merchant dashboard reads the same catalog from ``/api/v1/wallet-templates``,
    but that route authenticates as a merchant. This is the admin-authenticated
    door to the identical payload (``wallets.templates`` is the one source of
    truth for the backend renderers and both frontends).
    """

    permission_classes = _STUDIO

    @extend_schema(responses=WalletTemplateListSerializer)
    def get(self, request: Request) -> Response:
        from django.conf import settings

        from wallets import templates as templates_mod

        return Response(
            {
                "templates": templates_mod.template_choices(),
                "platform_logo_url": getattr(settings, "WALLET_PLATFORM_LOGO_URL", ""),
                "platform_label": getattr(settings, "WALLET_PLATFORM_LABEL", ""),
            }
        )


class WalletStudioUploadView(AdminAPIView):
    """POST /wallet-studio/uploads — store stamp icons / strip artwork.

    The merchant dashboard has its own ``/uploads``; the studio needs the same
    capability behind admin auth. Both route through ``common.uploads``, so the
    two endpoints can never disagree about what image is acceptable.
    """

    permission_classes = _STUDIO
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=None, responses=None)
    def post(self, request: Request) -> Response:
        path = uploads.save_image(request.FILES.get("file"), prefix="wallet-studio")
        return Response({"url": uploads.absolute_url(request, path)}, status=201)


class MerchantCardRepublishView(AdminAPIView):
    """POST /…/republish — push the saved design to every live pass on this card.

    Deliberately explicit rather than a side effect of saving: an admin iterating
    on a design would otherwise fire a wallet push to every holder on each
    keystroke-to-save. Returns the number of passes queued so the cost is visible
    before and after.
    """

    permission_classes = _STUDIO

    @extend_schema(responses=RepublishResultSerializer)
    def post(self, request: Request, merchant_id: str, card_id: str) -> Response:
        card = _card_for(merchant_id, card_id)

        from wallets import service as wallet_service
        from wallets.tasks import sync_google_class

        sync_google_class.delay(str(card.id))

        count = 0
        for customer_card in CustomerCard.objects.filter(card=card).iterator():
            wallet_service.push_update(customer_card)
            count += 1

        audit.record(
            request,
            "wallet_studio.republish",
            target_type="card",
            target_id=str(card.id),
            metadata={"merchant_id": str(card.merchant_id), "customer_cards": count},
        )
        return Response(
            RepublishResultSerializer({"customer_cards": count, "google_class_synced": True}).data
        )
