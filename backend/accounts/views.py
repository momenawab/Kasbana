"""Account-lifecycle endpoints (Phase 1.5 · contract Auth/Account/Settings).

Self-serve signup (starts the trial), password recovery, staff-invite accept,
session context (``/me``), and business/account settings. Public endpoints use
``AllowAny`` (``security: []`` in the contract); the rest resolve the caller's
``StaffUser`` for merchant scoping.
"""

from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import PasswordResetToken, StaffInvite
from accounts.serializers import (
    AccountSettingsOutSerializer,
    AccountSettingsSerializer,
    BusinessSettingsSerializer,
    ForgotSerializer,
    InviteAcceptSerializer,
    InviteInfoSerializer,
    MeOutSerializer,
    MerchantOutSerializer,
    OkSerializer,
    PasswordChangeSerializer,
    ResetSerializer,
    SignupSerializer,
    TokenPairSerializer,
)
from accounts.services import merchant_payload, settings_for
from billing import entitlements
from common.errors import Conflict, TokenExpired
from common.middleware import resolve_staff
from common.permissions import CanManageCards, IsScannerOrAbove
from core.models import StaffUser
from core.tenancy import get_request_merchant

User = get_user_model()


def _token_pair(user: Any) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# ── Auth lifecycle (public) ──────────────────────────────────────────────────
class SignupView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=SignupSerializer, responses=TokenPairSerializer)
    def post(self, request: Request) -> Response:
        body = SignupSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if User.objects.filter(username__iexact=body.validated_data["email"]).exists():
            raise Conflict("An account with this email already exists.")
        staff = body.save()
        return Response(_token_pair(staff.user))


class ForgotView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=ForgotSerializer, responses=OkSerializer)
    def post(self, request: Request) -> Response:
        body = ForgotSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=body.validated_data["email"]).first()
        if user is not None:
            reset = PasswordResetToken.objects.create(user=user)
            send_mail(
                subject="Reset your Stampn password",
                message=f"Use this token to reset your password: {reset.token}",
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
        # Always 200 — never leak whether the email exists.
        return Response({"ok": True})


class ResetView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(request=ResetSerializer, responses=OkSerializer)
    def post(self, request: Request) -> Response:
        body = ResetSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reset = PasswordResetToken.objects.filter(token=body.validated_data["token"]).first()
        if reset is None or not reset.is_valid():
            raise TokenExpired("This reset link is invalid or has expired.")
        user = reset.user
        user.set_password(body.validated_data["password"])
        user.save(update_fields=["password"])
        reset.used_at = timezone.now()
        reset.save(update_fields=["used_at"])
        return Response({"ok": True})


class InviteView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def _resolve(self, token: str) -> StaffInvite:
        invite = (
            StaffInvite.objects.select_related("merchant", "location").filter(token=token).first()
        )
        if invite is None or not invite.is_valid():
            raise TokenExpired("This invite is invalid or has expired.")
        return invite

    @extend_schema(responses=InviteInfoSerializer)
    def get(self, request: Request, t: str) -> Response:
        invite = self._resolve(t)
        return Response(
            {"merchant_name": invite.merchant.name, "role": invite.role, "email": invite.email}
        )

    @extend_schema(request=InviteAcceptSerializer, responses=TokenPairSerializer)
    def post(self, request: Request, t: str) -> Response:
        invite = self._resolve(t)
        body = InviteAcceptSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if User.objects.filter(username__iexact=invite.email).exists():
            raise Conflict("An account with this email already exists.")

        user = User(username=invite.email, email=invite.email)
        user.set_password(body.validated_data["password"])
        user.save()
        StaffUser.objects.create(
            merchant=invite.merchant, user=user, role=invite.role, location=invite.location
        )
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["accepted_at"])
        return Response(_token_pair(user))


# ── Session + settings (authenticated) ───────────────────────────────────────
class MeView(APIView):
    permission_classes = [IsScannerOrAbove]
    # A suspended merchant's staff must still load /me so the dashboard can show
    # the "account suspended" state (every other endpoint stays blocked).
    allow_suspended = True

    @extend_schema(responses=MeOutSerializer)
    def get(self, request: Request) -> Response:
        merchant = get_request_merchant(request)
        staff = cast(StaffUser, resolve_staff(request))  # non-null: IsScannerOrAbove passed
        payload = {
            "merchant": merchant_payload(merchant),
            "entitlements": entitlements.describe(merchant),
            "staff": {"role": staff.role},
        }
        # Set by MerchantJWTAuthentication for an impersonation token (Phase 6) —
        # the dashboard shows its "viewing as" banner off this.
        imp = getattr(request, "impersonation", None)
        if imp is not None:
            payload["impersonation"] = {
                "admin_email": imp.admin_email,
                "expires_at": imp.expires_at,
            }
        return Response(payload)


class SettingsBusinessView(APIView):
    # Branding lives here, so the Designer can edit it (alongside Owner/Admin).
    permission_classes = [CanManageCards]

    @extend_schema(responses=MerchantOutSerializer)
    def get(self, request: Request) -> Response:
        return Response(merchant_payload(get_request_merchant(request)))

    @extend_schema(request=BusinessSettingsSerializer, responses=MerchantOutSerializer)
    def patch(self, request: Request) -> Response:
        body = BusinessSettingsSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        merchant = get_request_merchant(request)
        for field in ("name", "legal_name", "logo_url", "color_bg", "color_fg"):
            if field in data:
                setattr(merchant, field, data[field] or "")
        merchant.save()

        s = settings_for(merchant)
        if "contact" in data:
            s.contact_phone = data["contact"].get("phone", s.contact_phone)
            s.contact_email = data["contact"].get("email", s.contact_email)
        if "address" in data:
            s.address = data["address"]

        # Branded enrollment copy is a paid feature — enforce the capability only
        # when the merchant actually sends it (leaves other settings ungated).
        if "enroll_headline" in data or "enroll_tagline" in data:
            entitlements.enforce(merchant, "custom_branding")
            if "enroll_headline" in data:
                s.enroll_headline = data["enroll_headline"]
            if "enroll_tagline" in data:
                s.enroll_tagline = data["enroll_tagline"]
        s.save()
        return Response(merchant_payload(merchant))


class SettingsAccountView(APIView):
    permission_classes = [IsScannerOrAbove]

    def _payload(self, s: Any) -> dict[str, Any]:
        return {
            "language": s.language,
            "notifications": {"email": s.notif_email, "whatsapp": s.notif_whatsapp},
        }

    @extend_schema(responses=AccountSettingsOutSerializer)
    def get(self, request: Request) -> Response:
        return Response(self._payload(settings_for(get_request_merchant(request))))

    @extend_schema(request=AccountSettingsSerializer, responses=AccountSettingsOutSerializer)
    def patch(self, request: Request) -> Response:
        body = AccountSettingsSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        data = body.validated_data

        s = settings_for(get_request_merchant(request))
        if "language" in data:
            s.language = data["language"]
        if "notifications" in data:
            s.notif_email = data["notifications"].get("email", s.notif_email)
            s.notif_whatsapp = data["notifications"].get("whatsapp", s.notif_whatsapp)
        s.save()
        return Response(self._payload(s))


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses=OkSerializer)
    def post(self, request: Request) -> Response:
        body = PasswordChangeSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user: Any = request.user  # IsAuthenticated -> a concrete User
        if not user.check_password(body.validated_data["current"]):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"current": ["Current password is incorrect."]})
        user.set_password(body.validated_data["new"])
        user.save(update_fields=["password"])
        return Response({"ok": True})
