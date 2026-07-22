"""Convert-To-Merchant — the point of the whole CRM.

Sales closes a lead and everything they already typed becomes the merchant's
account: no re-entry, no copy-paste, no second system. That goal is the reason
this module exists at all, and it is also the reason it is careful.

Two rules it will not bend:

**It does not grant paid access.** Provisioning goes through
``accounts.services.provision_merchant``, the same function self-serve signup
calls, which starts the ordinary trial. When Sales has sold a plan, that plan is
what the merchant *trials on* — ``Subscription.plan`` is documented as "the plan
the merchant picked at the gate, what they trial on and what Paymob auto-charges
at trial end" — and payment activates it through the usual webhook. Convert
never calls ``activate_plan``. Doing so would grant a paid plan to someone who
has not paid, and create the second payment path §12.3 exists to prevent.

**It does not set a password.** A lead never gave us one, and Sales must not
invent one they would then have to tell the merchant. The owner is created with
an unusable password and emailed a link to set their own. That link is a
``PasswordResetToken`` rather than a ``StaffInvite`` because the invite flow
(``accounts.views.InviteView``) refuses an email that already has an account —
and by this point the owner *does* have one. Its expiry is set explicitly to the
invite TTL: the one-hour reset default is right for "I forgot my password, send
it now" and wrong for "welcome, set up your account", which someone reads after
lunch.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import INVITE_TTL_DAYS, PasswordResetToken
from accounts.services import provision_merchant
from billing.models import Plan, Subscription
from billing.services import subscription_for
from console import crm, crm_service
from console.models import AdminUser, Lead
from core.enums import PlanTier
from core.models import Location, StaffUser

logger = logging.getLogger(__name__)

# What the first branch is called when the lead gives us nothing better. The
# lead has an area and an address but never a branch name — a shop's first
# location is just "the shop".
DEFAULT_BRANCH_NAME = "Main Branch"


class ConversionError(Exception):
    """A lead that cannot be converted, with a reason meant for a salesperson."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _resolve_plan(plan_key: str) -> tuple[str, Plan | None]:
    """Map a plan key from the Convert form onto (tier, negotiated plan row).

    Enterprise is two-part in this codebase: the *tier* says ENTERPRISE and
    ``Subscription.enterprise_plan`` names which negotiated deal. A public tier
    (Starter/Growth/Chain) is just itself.
    """
    if not plan_key:
        return "", None

    if plan_key in PlanTier.values:
        return plan_key, None

    # Not a tier, so it must be a negotiated plan row (Enterprise Gold, …).
    plan = Plan.objects.filter(key=plan_key, archived=False).first()
    if plan is None:
        raise ConversionError("UNKNOWN_PLAN", f"'{plan_key}' is not a live plan.")
    if plan.is_public:
        # Mirrors assign_enterprise_plan's guard: a public tier is bought at
        # self-serve. Putting a merchant on ENTERPRISE while resolving to
        # Growth's limits is a confusing state with no legitimate use.
        raise ConversionError(
            "PUBLIC_PLAN_NOT_NEGOTIABLE",
            f"{plan.key} is a public plan — pick its tier instead.",
        )
    return PlanTier.ENTERPRISE, plan


def _apply_sold_plan(merchant, plan_key: str) -> Subscription:
    """Put the merchant on the plan Sales sold — as a *trial*, not as access.

    Sets what the merchant trials on and what they will be charged for at trial
    end. Status is left at TRIALING by ``subscription_for``; only the payment
    webhook makes it ACTIVE.
    """
    sub = subscription_for(merchant)
    tier, negotiated = _resolve_plan(plan_key)
    if not tier:
        return sub  # no plan sold — the default trial stands

    sub.plan = tier
    sub.enterprise_plan = negotiated
    sub.save(update_fields=["plan", "enterprise_plan", "updated_at"])

    # Merchant.plan mirrors the tier so the rest of the app reads it cheaply;
    # Subscription stays the source of truth for access.
    if merchant.plan != tier:
        merchant.plan = tier
        merchant.save(update_fields=["plan"])
    return sub


def _send_setup_email(staff: StaffUser, merchant_name: str) -> bool:
    """Email the new owner a link to set their own password. Returns whether it
    went out.

    Best-effort by design: the merchant, branch and owner are already committed
    by the time this runs, and a bounced SMTP call must not roll that back and
    leave Sales staring at a lead that failed to convert for a reason they
    cannot act on. If it fails, the console's existing "Send password reset"
    support action re-sends it.

    Best-effort is not the same as silent, though. ``fail_silently=True`` here
    used to swallow a misconfigured SMTP host whole: no email, no log, and a
    timeline entry claiming the link had been sent — the merchant simply never
    heard from us and nobody knew. So we catch and *log* instead, and report the
    outcome upward so the conversion response can say the link needs re-sending.
    """
    reset = PasswordResetToken.objects.create(
        user=staff.user,
        expires_at=timezone.now() + timedelta(days=INVITE_TTL_DAYS),
    )
    try:
        sent = send_mail(
            subject=f"Welcome to Stampn — set up {merchant_name}",
            message=(
                f"Your Stampn account for {merchant_name} is ready.\n\n"
                "Set your password to get started:\n\n"
                f"{settings.DASHBOARD_BASE_URL}/reset/{reset.token}\n\n"
                f"This link is valid for {INVITE_TTL_DAYS} days."
            ),
            from_email=None,
            recipient_list=[staff.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "convert: setup email to %s for %s failed", staff.user.email, merchant_name
        )
        return False
    return bool(sent)


@transaction.atomic
def convert_lead(lead: Lead, *, actor: AdminUser, plan_key: str = "") -> dict:
    """Turn ``lead`` into a live merchant. Returns the created objects.

    Atomic: a lead is either fully converted — merchant, owner, branch,
    subscription, timeline, and the lead itself marked Converted — or nothing
    happened. A half-converted lead is the worst outcome available here, because
    the next attempt would collide with the merchant the first one left behind.
    """
    if lead.is_converted:
        raise ConversionError(
            "ALREADY_CONVERTED",
            (
                f"{lead.business_name} was already converted on " f"{lead.converted_at:%d %b %Y}."
                if lead.converted_at
                else "Already converted."
            ),
        )
    if not lead.email:
        # The owner account is keyed on email and the setup link is emailed to
        # it. Without one there is no account to make and no way to hand it over.
        raise ConversionError(
            "EMAIL_REQUIRED",
            "Add an email address to this lead before converting it — "
            "the owner's login and setup link both need one.",
        )

    from django.contrib.auth import get_user_model

    if get_user_model().objects.filter(username__iexact=lead.email).exists():
        raise ConversionError(
            "EMAIL_IN_USE",
            f"{lead.email} already has a Stampn account. "
            "Link this lead to that merchant instead of converting it.",
        )

    staff = provision_merchant(
        business_name=lead.business_name,
        owner_name=lead.name or lead.business_name,
        email=lead.email,
        phone=lead.phone,
        password=None,  # unusable — the owner sets their own via the link below
        logo_url=lead.logo_url,
    )
    merchant = staff.merchant

    sub = _apply_sold_plan(merchant, plan_key)

    # The first branch. Prefilled from whatever the lead knows: its address, or
    # failing that its area, which is the only location most walk-in leads have.
    branch = Location.objects.create(
        merchant=merchant,
        name=DEFAULT_BRANCH_NAME,
        address=lead.address or lead.area,
    )

    lead.converted_merchant = merchant
    lead.converted_at = timezone.now()
    lead.status = crm.LeadStatus.CONVERTED
    lead.save(update_fields=["converted_merchant", "converted_at", "status", "updated_at"])

    # Before the timeline entry, because the entry now states which of the two
    # things happened. A conversion whose email bounced still converted — it just
    # leaves an owner who has heard nothing, and the timeline must say so rather
    # than record a send that never occurred.
    email_sent = _send_setup_email(staff, merchant.name)

    crm_service.log_activity(
        lead,
        crm.ActivityKind.CONVERTED_TO_MERCHANT,
        "Converted To Merchant",
        description=(
            f"{merchant.name} created on the {sub.plan} plan. "
            + (
                f"Setup link sent to {lead.email}."
                if email_sent
                else f"Setup link to {lead.email} FAILED to send — re-send it from Support."
            )
        ),
        actor=actor,
    )

    return {
        "merchant": merchant,
        "owner": staff,
        "branch": branch,
        "subscription": sub,
        "email_sent": email_sent,
    }
