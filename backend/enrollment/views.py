"""Enrollment endpoints (contract §3.6 · Phase 1.1 · public).

GET  /enroll/{token}  — program details for the join page.
POST /enroll/{token}  — create a CustomerCard (PDPL consent), record the opening
                        ledger event, provision Apple + Google passes.
"""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from common.errors import AlreadyEnrolled
from core import ledger
from core.models import CustomerCard
from enrollment.serializers import (
    EnrollLandingSerializer,
    EnrollRequestSerializer,
    EnrollResponseSerializer,
)
from enrollment.tokens import resolve_active_token
from wallets import service as wallet


class EnrollView(APIView):
    """Public join flow behind a QR token."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def _get_token_or_404(self, token: str):
        row = resolve_active_token(token)  # raises TokenExpired (410) if expired
        if row is None:
            from rest_framework.exceptions import NotFound

            raise NotFound("Enrollment link not found.")
        return row

    @extend_schema(responses=EnrollLandingSerializer)
    def get(self, request: Request, token: str) -> Response:
        from billing import entitlements

        row = self._get_token_or_404(token)
        card = row.card
        merchant = row.merchant

        # Branded enrollment: on custom_branding plans the merchant's own copy
        # shows and the "Powered by Stampn" footer is hidden (white-label).
        branded = entitlements.check(merchant, "custom_branding")
        settings = getattr(merchant, "settings", None)
        headline = (getattr(settings, "enroll_headline", "") or "") if branded else ""
        tagline = (getattr(settings, "enroll_tagline", "") or "") if branded else ""

        data = EnrollLandingSerializer(
            {
                "merchant_name": merchant.name,
                "card_name": card.name,
                "reward_title": card.reward_title,
                "stamps_required": card.stamps_required,
                "color_bg": card.color_bg or merchant.color_bg,
                "color_fg": card.color_fg or merchant.color_fg,
                "logo_url": card.logo_url or merchant.logo_url,
                "headline": headline,
                "tagline": tagline,
                "show_powered_by": not branded,
            }
        ).data
        return Response(data)

    @extend_schema(request=EnrollRequestSerializer, responses=EnrollResponseSerializer)
    def post(self, request: Request, token: str) -> Response:
        row = self._get_token_or_404(token)
        card = row.card

        body = EnrollRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        phone = body.validated_data["customer_phone"]
        name = body.validated_data["customer_name"]
        email = body.validated_data["customer_email"]
        birthday = body.validated_data["birthday"]

        # One card per phone per program (contract §3.4 uniqueness).
        if CustomerCard.objects.filter(card=card, customer_phone=phone).exists():
            raise AlreadyEnrolled()

        try:
            with transaction.atomic():
                customer_card = CustomerCard.objects.create(
                    card=card,
                    merchant=card.merchant,
                    customer_phone=phone,
                    customer_name=name,
                    customer_email=email,
                    birthday=birthday,
                    consent_at=timezone.now(),
                    enrolled_at=timezone.now(),
                )
                ledger.record_enrollment(customer_card)
        except IntegrityError:
            # Lost the race against a concurrent enroll of the same phone.
            raise AlreadyEnrolled()

        # Referral conversion: if joined via ?ref=<referrer>, grant bonus stamps
        # to both. Best-effort, heavily guarded (see enrollment.referrals).
        from enrollment.referrals import apply_referral

        referral = apply_referral(card, customer_card, body.validated_data.get("ref"))
        if referral is not None:
            customer_card.refresh_from_db(fields=["stamp_count"])
            wallet.push_update(referral.referrer)
            wallet.push_update(customer_card)

        # Engage automation (Phase 1.7): fire the welcome trigger on a fresh
        # enrollment. Best-effort — no-ops unless the merchant enabled it.
        from messaging.tasks import fire_for_customer

        fire_for_customer(card.merchant, customer_card, "welcome")

        # Provision passes (Apple + Google). Returns null URLs if creds absent.
        result = wallet.provision(customer_card)

        # The new customer's own share link, so the success page can invite them
        # to refer friends (only when referrals are enabled for this program).
        referral_url = ""
        if card.referral_enabled:
            referral_url = f"{settings.ENROLL_BASE_URL}/enroll/{token}?ref={customer_card.id}"

        payload = EnrollResponseSerializer(
            {
                "customer_card_id": customer_card.id,
                "stamp_count": customer_card.stamp_count,
                "stamps_required": card.stamps_required,
                "apple_pass_url": result.apple_pass_url,
                "google_save_url": result.google_save_url,
                "referral_url": referral_url,
            }
        ).data
        return Response(payload, status=status.HTTP_201_CREATED)
