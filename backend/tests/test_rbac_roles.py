"""Role-based access for the lateral roles (Marketing / Designer).

The hierarchical roles (Owner/Admin/Scanner) are covered elsewhere; here we
prove the new lateral roles see only their own area: Designer → cards/branding,
Marketing → engagement (campaigns/customers/analytics), and that each is locked
out of the other's area + owner/admin-only surfaces.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.enums import Role
from tests import factories

pytestmark = pytest.mark.django_db


def _client(merchant, role):
    staff = factories.StaffUserFactory(merchant=merchant, role=role)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff.user).access_token}"
    )
    return client


# ── Designer: cards yes, engagement/locations/billing no ──────────────────────
def test_designer_can_access_cards(merchant):
    resp = _client(merchant, Role.DESIGNER).get("/api/v1/cards")
    assert resp.status_code == 200


def test_designer_cannot_access_campaigns(merchant):
    resp = _client(merchant, Role.DESIGNER).get("/api/v1/campaigns")
    assert resp.status_code == 403


def test_designer_cannot_access_customers(merchant):
    resp = _client(merchant, Role.DESIGNER).get("/api/v1/customers")
    assert resp.status_code == 403


def test_designer_cannot_access_billing(merchant):
    resp = _client(merchant, Role.DESIGNER).get("/api/v1/billing")
    assert resp.status_code == 403


# ── Marketing: engagement yes, cards/locations/billing no ─────────────────────
def test_marketing_can_access_campaigns_and_customers(merchant):
    client = _client(merchant, Role.MARKETING)
    assert client.get("/api/v1/campaigns").status_code == 200
    assert client.get("/api/v1/customers").status_code == 200


def test_marketing_cannot_access_cards(merchant):
    resp = _client(merchant, Role.MARKETING).get("/api/v1/cards")
    assert resp.status_code == 403


def test_marketing_cannot_access_locations(merchant):
    resp = _client(merchant, Role.MARKETING).get("/api/v1/locations")
    assert resp.status_code == 403


# ── Both lateral roles share insights but not owner/admin-only surfaces ───────
def test_both_lateral_roles_see_analytics(merchant):
    for role in (Role.MARKETING, Role.DESIGNER):
        resp = _client(merchant, role).get("/api/v1/analytics/summary")
        assert resp.status_code == 200, role


def test_lateral_roles_cannot_manage_team(merchant):
    for role in (Role.MARKETING, Role.DESIGNER):
        resp = _client(merchant, role).get("/api/v1/staff")
        assert resp.status_code == 403, role


def test_lateral_roles_can_scan(merchant):
    """Every staff role can run the till."""
    card = factories.CardFactory(merchant=merchant, stamps_required=5)
    for role in (Role.MARKETING, Role.DESIGNER):
        cc = factories.CustomerCardFactory(card=card, merchant=merchant)
        resp = _client(merchant, role).post(
            "/api/v1/loyalty/stamp", {"customer_card_id": str(cc.id)}, format="json"
        )
        assert resp.status_code == 200, role


# ── Specialized roles gated by plan (specialized_roles capability, Growth+) ────
def test_starter_plan_cannot_invite_specialized_role(merchant):
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(merchant, PlanTier.STARTER)  # no specialized_roles
    resp = _client(merchant, Role.OWNER).post(
        "/api/v1/staff/invite", {"email": "m@x.co", "role": "MARKETING"}, format="json"
    )
    assert resp.status_code == 402


def test_growth_plan_can_invite_specialized_role(merchant):
    from billing.services import activate_plan
    from core.enums import PlanTier

    activate_plan(merchant, PlanTier.GROWTH)  # specialized_roles on
    resp = _client(merchant, Role.OWNER).post(
        "/api/v1/staff/invite", {"email": "d@x.co", "role": "DESIGNER"}, format="json"
    )
    assert resp.status_code == 201
