"""Support tools & impersonation endpoints (Phase 6).

Impersonation (start/end/list), support actions (send password reset, resend a
staff invite, clear a stuck checkout), the support-notes thread, and the
per-merchant activity timeline. Mutations are gated to Support/Super-admin —
deliberately NOT Finance: support tools never touch billing (the impersonation
token itself is blocked from billing endpoints in ``common.auth``). Reads are
open to any admin, matching every other console screen.
"""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import INVITE_TTL_DAYS, PasswordResetToken, StaffInvite
from billing.services import subscription_for
from console import activity, audit
from console.impersonation import end_impersonation, impersonation_target, start_impersonation
from console.models import AdminUser, Impersonation, SupportNote
from console.permissions import AdminAPIView, IsAdminUser, IsSupportAdmin
from console.serializers_support import (
    ActivityEventSerializer,
    ImpersonateRequestSerializer,
    ImpersonateResponseSerializer,
    ImpersonationEndSerializer,
    ImpersonationSerializer,
    OkSerializer,
    ReasonOnlySerializer,
    ResendInviteSerializer,
    SupportNoteCreateSerializer,
    SupportNoteSerializer,
)
from core.models import Merchant


def _imp_row(imp: Impersonation) -> dict:
    return {
        "id": imp.id,
        "admin_email": imp.admin_email,
        "target_email": imp.target_email,
        "reason": imp.reason,
        "created_at": imp.created_at,
        "expires_at": imp.expires_at,
        "ended_at": imp.ended_at,
        "active": imp.is_active(),
    }


class ImpersonationListView(AdminAPIView):
    """GET /merchants/{id}/impersonations — recent sessions (any admin)."""

    @extend_schema(responses=ImpersonationSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        rows = [_imp_row(i) for i in Impersonation.objects.filter(merchant_id=merchant_id)[:10]]
        return Response(ImpersonationSerializer(rows, many=True).data)


class ImpersonateView(AdminAPIView):
    """POST /merchants/{id}/impersonate — mint a view-as-merchant session."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=ImpersonateRequestSerializer, responses=ImpersonateResponseSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = ImpersonateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        target = impersonation_target(merchant)
        if target is None:
            return Response(
                {
                    "error": {
                        "code": "NO_ACTIVE_STAFF",
                        "message": "This merchant has no active staff identity to impersonate.",
                    }
                },
                status=409,
            )
        admin = cast(AdminUser, request.user)  # non-null: IsSupportAdmin passed
        imp, access = start_impersonation(admin, merchant, target, body.validated_data["reason"])
        audit.record(
            request,
            "impersonation.start",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={
                "impersonation_id": str(imp.id),
                "target_email": imp.target_email,
                "reason": imp.reason,
                "expires_at": imp.expires_at.isoformat(),
            },
        )
        return Response(
            {
                "impersonation_id": imp.id,
                "access": access,
                "target_email": imp.target_email,
                "expires_at": imp.expires_at,
            }
        )


class ImpersonationEndView(AdminAPIView):
    """POST /impersonate/end {impersonation_id} — kill a session server-side."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=ImpersonationEndSerializer, responses=ImpersonationSerializer)
    def post(self, request: Request) -> Response:
        body = ImpersonationEndSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        imp = get_object_or_404(Impersonation, pk=body.validated_data["impersonation_id"])
        end_impersonation(imp)
        audit.record(
            request,
            "impersonation.end",
            target_type="merchant",
            target_id=str(imp.merchant_id),
            metadata={"impersonation_id": str(imp.id)},
        )
        return Response(ImpersonationSerializer(_imp_row(imp)).data)


class SendPasswordResetView(AdminAPIView):
    """POST /merchants/{id}/support/send-password-reset — email the owner a reset link."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=None, responses=OkSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        target = impersonation_target(merchant)  # owner, else any active staff
        if target is None or not target.user.email:
            return Response(
                {
                    "error": {
                        "code": "NO_OWNER_EMAIL",
                        "message": "This merchant has no active staff with an email address.",
                    }
                },
                status=409,
            )
        reset = PasswordResetToken.objects.create(user=target.user)
        send_mail(
            subject="Reset your Stampn password",
            message=(
                "A password reset was requested for your Stampn account by our "
                "support team. Set a new password here:\n\n"
                f"{settings.DASHBOARD_BASE_URL}/reset/{reset.token}\n\n"
                "The link expires in 1 hour. If you didn't ask support for this, "
                "you can ignore this email.\n\n— Stampn"
            ),
            from_email=None,
            recipient_list=[target.user.email],
            fail_silently=True,
        )
        audit.record(
            request,
            "support.send_password_reset",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"email": target.user.email},
        )
        return Response({"ok": True})


class ResendInviteView(AdminAPIView):
    """POST /merchants/{id}/support/resend-invite {email} — refresh + re-email it."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=ResendInviteSerializer, responses=OkSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = ResendInviteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        email = body.validated_data["email"]

        invite = (
            StaffInvite.objects.filter(
                merchant=merchant, email__iexact=email, accepted_at__isnull=True
            )
            .order_by("-created_at")
            .first()
        )
        if invite is None:
            return Response(
                {
                    "error": {
                        "code": "INVITE_NOT_FOUND",
                        "message": "No pending invite exists for this email.",
                    }
                },
                status=404,
            )
        invite.expires_at = timezone.now() + timedelta(days=INVITE_TTL_DAYS)
        invite.save(update_fields=["expires_at"])
        send_mail(
            subject=f"You're invited to join {merchant.name} on Stampn",
            message=(
                f"You've been invited to join {merchant.name} as {invite.role}. "
                "Accept your invite here:\n\n"
                f"{settings.DASHBOARD_BASE_URL}/invite/{invite.token}\n\n"
                f"The link expires in {INVITE_TTL_DAYS} days.\n\n— Stampn"
            ),
            from_email=None,
            recipient_list=[invite.email],
            fail_silently=True,
        )
        audit.record(
            request,
            "support.resend_invite",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"email": invite.email, "invite_id": str(invite.id), "role": invite.role},
        )
        return Response({"ok": True})


class ClearStuckCheckoutView(AdminAPIView):
    """POST /merchants/{id}/support/clear-stuck-checkout — drop an abandoned
    pending checkout so subscribe/retry stop resolving through it."""

    permission_classes = [IsAdminUser, IsSupportAdmin]

    @extend_schema(request=ReasonOnlySerializer, responses=OkSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = ReasonOnlySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        sub = subscription_for(merchant)
        if not sub.pending_plan:
            return Response(
                {
                    "error": {
                        "code": "NO_PENDING_CHECKOUT",
                        "message": "This merchant has no pending checkout to clear.",
                    }
                },
                status=409,
            )
        before = {"pending_plan": sub.pending_plan, "gateway_ref": sub.gateway_ref}
        sub.pending_plan = ""
        sub.save(update_fields=["pending_plan", "updated_at"])
        audit.record(
            request,
            "support.clear_stuck_checkout",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"reason": body.validated_data["reason"], "before": before},
        )
        return Response({"ok": True})


class SupportNotesView(AdminAPIView):
    """GET /merchants/{id}/support/notes — thread. POST — add a note (Support+)."""

    def get_permissions(self):
        classes = [IsAdminUser] if self.request.method == "GET" else [IsAdminUser, IsSupportAdmin]
        return [cls() for cls in classes]

    @extend_schema(responses=SupportNoteSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        notes = SupportNote.objects.filter(merchant_id=merchant_id)[:50]
        rows = [
            {
                "id": n.id,
                "admin_email": n.admin_email,
                "body": n.body,
                "created_at": n.created_at,
            }
            for n in notes
        ]
        return Response(SupportNoteSerializer(rows, many=True).data)

    @extend_schema(request=SupportNoteCreateSerializer, responses=SupportNoteSerializer)
    def post(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        body = SupportNoteCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin = cast(AdminUser, request.user)  # non-null: IsSupportAdmin passed
        note = SupportNote.objects.create(
            merchant=merchant,
            admin=admin,
            admin_email=admin.email,
            body=body.validated_data["body"],
        )
        audit.record(
            request,
            "support.note",
            target_type="merchant",
            target_id=str(merchant.id),
            metadata={"note_id": str(note.id)},
        )
        return Response(
            SupportNoteSerializer(
                {
                    "id": note.id,
                    "admin_email": note.admin_email,
                    "body": note.body,
                    "created_at": note.created_at,
                }
            ).data,
            status=201,
        )


class ActivityView(AdminAPIView):
    """GET /merchants/{id}/activity — cross-sourced timeline (any admin)."""

    @extend_schema(responses=ActivityEventSerializer(many=True))
    def get(self, request: Request, merchant_id: str) -> Response:
        merchant = get_object_or_404(Merchant, pk=merchant_id)
        return Response(ActivityEventSerializer(activity.timeline(merchant), many=True).data)
