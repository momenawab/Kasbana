"""Account services (Phase 1.5) — provisioning + settings access + payload builders."""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from accounts.models import MerchantSettings
from billing.services import subscription_for
from billing.wire import plan_to_wire, status_to_wire
from core.enums import Role
from core.models import Merchant, StaffUser

User = get_user_model()
logger = logging.getLogger(__name__)


def settings_for(merchant: Merchant) -> MerchantSettings:
    """The merchant's settings row, created lazily. Idempotent."""
    obj, _ = MerchantSettings.objects.get_or_create(merchant=merchant)
    return obj


@transaction.atomic
def provision_merchant(
    *,
    business_name: str,
    owner_name: str,
    email: str,
    phone: str = "",
    password: str | None = None,
    logo_url: str = "",
) -> StaffUser:
    """Create a merchant and its owner, and start the trial. Returns the owner.

    The one way a merchant comes into existence. Both entry points call it —
    self-serve signup (``accounts.serializers.SignupSerializer``) and Sales
    converting a lead (``console.crm_convert``) — because a merchant that exists
    in one flow's shape but not the other's is the kind of drift nobody notices
    until support cannot explain why an account has no settings row.

    ``password=None`` creates the owner with an *unusable* password: the account
    exists and can be assigned, but nothing can authenticate as it until the
    person sets their own. That is the conversion case — a lead never handed us
    a password, and Sales must not invent one. The caller is then responsible
    for emailing them a set-password link (see ``console.crm_convert``).

    Does NOT grant paid access: ``subscription_for`` starts the ordinary trial
    and payment activates the plan through the usual webhook (§12.3). Anything
    that wants a different plan sets it on the returned subscription afterwards.
    """
    user = User(username=email, email=email, first_name=owner_name[:150])
    if password:
        user.set_password(password)
    else:
        user.set_unusable_password()
    user.save()

    merchant = Merchant.objects.create(
        name=business_name,
        slug=unique_slug(business_name),
        logo_url=logo_url,
    )
    staff = StaffUser.objects.create(merchant=merchant, user=user, role=Role.OWNER)

    s = settings_for(merchant)
    s.contact_email = email
    s.contact_phone = phone
    s.save(update_fields=["contact_email", "contact_phone", "updated_at"])

    subscription_for(merchant)  # starts the 14-day trial

    return staff


def unique_slug(name: str) -> str:
    """A unique merchant slug derived from ``name`` (``-2``, ``-3`` on collision)."""
    base = slugify(name) or "merchant"
    slug, n = base, 1
    while Merchant.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


def merchant_payload(merchant: Merchant) -> dict[str, Any]:
    """Contract ``Merchant`` object with wire-mapped ``plan`` / ``status``."""
    sub = subscription_for(merchant)
    s = settings_for(merchant)
    return {
        "id": str(merchant.id),
        "name": merchant.name,
        "legal_name": merchant.legal_name,
        "slug": merchant.slug,
        "status": status_to_wire(merchant, sub),
        "plan": plan_to_wire(sub),
        "trial_ends_at": sub.trial_ends_at,
        "logo_url": merchant.logo_url or None,
        "address": s.address,
        "color_bg": merchant.color_bg,
        "color_fg": merchant.color_fg,
        "enroll_headline": s.enroll_headline,
        "enroll_tagline": s.enroll_tagline,
        "phone": s.contact_phone,
        "facebook_url": s.facebook_url,
        "instagram_url": s.instagram_url,
        "tiktok_url": s.tiktok_url,
        "whatsapp": s.whatsapp,
        "terms_url": s.terms_url,
        "branches": s.branches,
    }
