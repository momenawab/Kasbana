"""Convert-To-Merchant tests.

The lead CRM's payoff and its sharpest edge: this is the one lead action that
creates real, billable accounts. The tests that matter most here are the ones
asserting what conversion *must not* do — grant paid access without payment, or
put a password anywhere near Sales.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

from accounts.models import PasswordResetToken
from billing.models import Plan, Subscription
from billing.plans import BillingStatus
from console import crm, crm_convert
from console.auth import issue_admin_tokens
from console.crm_seed import ensure_seeded
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Lead
from core.enums import PlanTier, Role
from core.models import Location, Merchant, StaffUser

pytestmark = pytest.mark.django_db

ADMIN = "/api/admin/v1/leads"
User = get_user_model()


@pytest.fixture(autouse=True)
def seeded_choices():
    ensure_seeded()


@pytest.fixture
def sales():
    a = AdminUser(email="sales@stampn.net", name="Nour Sales", role=AdminRole.SALES)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def finance():
    a = AdminUser(email="fin@stampn.net", role=AdminRole.FINANCE)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _lead(**overrides) -> Lead:
    return Lead.objects.create(
        **{
            "business_name": "Bloom Café",
            "name": "Ali Hassan",
            "phone": "01000000000",
            "email": "ali@bloomcafe.com",
            "address": "12 Nile St, Zamalek",
            "area": "Zamalek",
            **overrides,
        }
    )


# ── The happy path ──────────────────────────────────────────────────────────
def test_convert_creates_merchant_owner_branch_and_subscription(sales):
    lead = _lead()
    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")
    assert res.status_code == 201

    merchant = Merchant.objects.get()
    assert merchant.name == "Bloom Café"
    assert merchant.slug  # slugified + de-duplicated by provision_merchant

    owner = StaffUser.objects.get()
    assert owner.merchant == merchant
    assert owner.role == Role.OWNER
    assert owner.user.email == "ali@bloomcafe.com"

    branch = Location.objects.get()
    assert branch.merchant == merchant
    assert branch.name == "Main Branch"
    assert branch.address == "12 Nile St, Zamalek"  # carried from the lead

    assert Subscription.objects.filter(merchant=merchant).exists()


def test_convert_marks_the_lead_and_links_the_merchant(sales):
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    lead.refresh_from_db()
    assert lead.status == crm.LeadStatus.CONVERTED
    assert lead.converted_merchant == Merchant.objects.get()
    assert lead.converted_at is not None
    assert lead.is_converted


def test_convert_lands_on_the_timeline_and_the_audit_log(sales):
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    activity = lead.activities.get(kind=crm.ActivityKind.CONVERTED_TO_MERCHANT)
    assert activity.actor == sales
    assert "Bloom Café" in activity.description
    assert AdminAuditLog.objects.filter(action="lead.convert").exists()


def test_branch_falls_back_to_the_area_when_there_is_no_address(sales):
    lead = _lead(address="", area="Maadi")
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")
    assert Location.objects.get().address == "Maadi"


# ── The owner's password ────────────────────────────────────────────────────
def test_the_owner_cannot_be_logged_into_until_they_set_a_password(sales):
    """Sales must never know, set, or be able to use the merchant's password."""
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    user = User.objects.get(username="ali@bloomcafe.com")
    assert not user.has_usable_password()


def test_convert_emails_a_setup_link_that_outlives_the_reset_default(sales):
    """A one-hour link is right for "I forgot my password"; it is wrong for
    "welcome, set up your account", read after lunch."""
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    token = PasswordResetToken.objects.get()
    assert token.user.email == "ali@bloomcafe.com"
    assert token.is_valid()
    # 7 days (INVITE_TTL_DAYS), not the 1-hour reset default.
    assert (token.expires_at - token.created_at).days >= 6

    assert len(mail.outbox) == 1
    assert token.token in mail.outbox[0].body
    assert "ali@bloomcafe.com" in mail.outbox[0].to


def test_the_owner_can_set_their_password_with_the_emailed_link(sales):
    """The link has to actually work — the invite flow would have refused this
    account for already existing."""
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")
    token = PasswordResetToken.objects.get().token

    res = APIClient().post(
        "/api/v1/auth/reset", {"token": token, "password": "newpassword1"}, format="json"
    )
    assert res.status_code == 200

    user = User.objects.get(username="ali@bloomcafe.com")
    assert user.has_usable_password()
    assert user.check_password("newpassword1")


# ── Billing: the rule Convert must not break ────────────────────────────────
def test_convert_never_grants_paid_access(sales):
    """§12.3: admin actions record the agreement; only the payment webhook
    grants access. If this ever goes ACTIVE, Convert has become a second way to
    get a paid plan for free."""
    lead = _lead(expected_plan="pro")
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {"plan_key": "GROWTH"}, format="json")

    sub = Subscription.objects.get()
    assert sub.status == BillingStatus.TRIALING
    assert sub.status != BillingStatus.ACTIVE


def test_the_sold_plan_becomes_what_the_merchant_trials_on(sales):
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {"plan_key": "GROWTH"}, format="json")

    sub = Subscription.objects.get()
    assert sub.plan == PlanTier.GROWTH
    assert sub.status == BillingStatus.TRIALING  # trialing *on* Growth
    assert Merchant.objects.get().plan == PlanTier.GROWTH


def test_the_trial_still_runs_when_no_plan_was_sold(sales):
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    sub = Subscription.objects.get()
    assert sub.status == BillingStatus.TRIALING
    assert sub.trial_ends_at is not None


def test_a_negotiated_enterprise_plan_is_handled_per_schema_support(sales):
    """Enterprise conversion depends on schema the Paymob rollout owns. Where it
    is present the negotiated plan is recorded; where it is held back the
    conversion is cleanly refused rather than crashing. One test, both branches."""
    plan = Plan.objects.create(key="enterprise_gold", name="Enterprise Gold", is_public=False)
    lead = _lead()
    res = _admin(sales).post(
        f"{ADMIN}/{lead.id}/convert", {"plan_key": "enterprise_gold"}, format="json"
    )

    if crm_convert.ENTERPRISE_SUPPORTED:
        assert res.status_code == 201
        sub = Subscription.objects.get()
        assert sub.plan == crm_convert._ENTERPRISE_TIER
        assert sub.enterprise_plan == plan
        assert sub.status == BillingStatus.TRIALING
    else:
        assert res.status_code == 409
        assert res.data["error"]["code"] == "ENTERPRISE_UNAVAILABLE"
        assert Merchant.objects.count() == 0  # nothing provisioned


def test_a_public_plan_row_cannot_be_assigned_as_negotiated(sales):
    """Mirrors assign_enterprise_plan's guard — otherwise a merchant sits on
    ENTERPRISE while resolving to Growth's limits."""
    Plan.objects.create(key="growth_public", name="Growth", is_public=True)
    lead = _lead()
    res = _admin(sales).post(
        f"{ADMIN}/{lead.id}/convert", {"plan_key": "growth_public"}, format="json"
    )
    assert res.status_code == 409
    assert res.data["error"]["code"] == "PUBLIC_PLAN_NOT_NEGOTIABLE"


def test_an_unknown_plan_is_rejected_and_nothing_is_created(sales):
    lead = _lead()
    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {"plan_key": "platinum"}, format="json")
    assert res.status_code == 400
    assert Merchant.objects.count() == 0  # the whole conversion rolled back


# ── Refusals ────────────────────────────────────────────────────────────────
def test_a_lead_without_an_email_cannot_be_converted(sales):
    """The owner's login is their email, and the setup link goes to it."""
    lead = _lead(email="")
    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "EMAIL_REQUIRED"
    assert Merchant.objects.count() == 0


def test_converting_twice_is_refused_rather_than_duplicating_the_merchant(sales):
    lead = _lead()
    assert _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json").status_code == 201

    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")
    assert res.status_code == 409
    assert res.data["error"]["code"] == "ALREADY_CONVERTED"
    assert Merchant.objects.count() == 1


def test_an_email_that_already_has_an_account_is_refused(sales):
    """Otherwise provision_merchant would create a second User on one email and
    the owner would never be able to log in to the right one."""
    User.objects.create_user(username="ali@bloomcafe.com", email="ali@bloomcafe.com")
    lead = _lead()

    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")
    assert res.status_code == 409
    assert res.data["error"]["code"] == "EMAIL_IN_USE"
    assert Merchant.objects.count() == 0


def test_a_failed_conversion_leaves_nothing_behind(sales):
    """Half a conversion is the worst outcome available: the retry would collide
    with the merchant the first attempt orphaned."""
    Plan.objects.create(key="growth_public", name="Growth", is_public=True)
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {"plan_key": "growth_public"}, format="json")

    assert Merchant.objects.count() == 0
    assert StaffUser.objects.count() == 0
    assert Location.objects.count() == 0
    assert User.objects.filter(username="ali@bloomcafe.com").count() == 0
    lead.refresh_from_db()
    assert not lead.is_converted


# ── Permissions ─────────────────────────────────────────────────────────────
def test_finance_cannot_convert_a_lead(finance):
    """Conversion is gated on LEADS_CONVERT, which only Sales and super-admin
    hold — it creates billable accounts, so it is worth granting separately."""
    lead = _lead()
    assert _admin(finance).post(f"{ADMIN}/{lead.id}/convert", {}, format="json").status_code == 403
    assert Merchant.objects.count() == 0


# ── Zero re-entry ───────────────────────────────────────────────────────────
def test_the_lead_logo_becomes_the_merchant_logo(sales):
    lead = _lead(logo_url="https://cdn.stampn.net/lead-logos/bloom.png")
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    assert Merchant.objects.get().logo_url == "https://cdn.stampn.net/lead-logos/bloom.png"


def test_the_merchants_contact_details_come_from_the_lead(sales):
    from accounts.services import settings_for

    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    s = settings_for(Merchant.objects.get())
    assert s.contact_email == "ali@bloomcafe.com"
    assert s.contact_phone == "01000000000"


def test_a_lead_with_no_owner_name_still_converts(sales):
    """Walk-in leads are often a business name and a phone number."""
    lead = _lead(name="")
    res = _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    assert res.status_code == 201
    assert User.objects.get().first_name == "Bloom Café"  # falls back to the business


# ── Signup still works through the shared provisioning ──────────────────────
def test_signup_and_convert_produce_the_same_shaped_merchant(sales):
    """The reason provisioning was extracted: one implementation, so a merchant
    cannot exist in one flow's shape but not the other's."""
    from accounts.services import settings_for

    APIClient().post(
        "/api/v1/auth/signup",
        {
            "business_name": "Signup Shop",
            "owner_name": "Sara",
            "email": "sara@signup.com",
            "phone": "01111111111",
            "password": "password123",
            "consent": True,
        },
        format="json",
    )
    lead = _lead()
    _admin(sales).post(f"{ADMIN}/{lead.id}/convert", {}, format="json")

    signed_up = Merchant.objects.get(name="Signup Shop")
    converted = Merchant.objects.get(name="Bloom Café")

    for merchant in (signed_up, converted):
        assert merchant.slug
        assert StaffUser.objects.filter(merchant=merchant, role=Role.OWNER).exists()
        assert Subscription.objects.filter(merchant=merchant).exists()
        assert settings_for(merchant).contact_email

    # The one deliberate difference: a signup chose their password, a converted
    # owner has not set one yet.
    assert User.objects.get(username="sara@signup.com").has_usable_password()
    assert not User.objects.get(username="ali@bloomcafe.com").has_usable_password()
