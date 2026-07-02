"""Merchant directory + detail tests (Phase 2).

Covers cross-tenant listing (an admin sees ALL merchants), search/filter, the
360° detail shape, admin-role auth, and — security-critical — that a merchant
token can't reach these cross-tenant endpoints.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminUser
from tests import factories

pytestmark = pytest.mark.django_db

LIST = "/api/admin/v1/merchants"


@pytest.fixture
def admin_user():
    a = AdminUser(email="ops@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def admin_client(admin_user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin_user)['access']}")
    return c


def test_list_is_cross_tenant(admin_client):
    factories.MerchantFactory(name="Cairo Coffee")
    factories.MerchantFactory(name="Alex Bakery")
    factories.MerchantFactory(name="Giza Grill")

    resp = admin_client.get(LIST)
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 3  # all three, no tenant scoping


def test_list_search_by_name(admin_client):
    factories.MerchantFactory(name="Cairo Coffee")
    factories.MerchantFactory(name="Alex Bakery")

    resp = admin_client.get(LIST, {"q": "cairo"})
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["name"] == "Cairo Coffee"


def test_list_row_has_counts(admin_client):
    merchant = factories.MerchantFactory()
    card = factories.CardFactory(merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant)

    row = admin_client.get(LIST).json()["results"][0]
    assert row["cards_count"] == 1
    assert row["customers_count"] == 2
    assert "plan" in row and "billing_status" in row


def test_detail_360(admin_client, merchant):
    factories.StaffUserFactory(merchant=merchant)  # owner-ish
    resp = admin_client.get(f"{LIST}/{merchant.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(merchant.id)
    assert "usage" in body and "wallet" in body and "owner" in body
    assert "admin_meta" in body


def test_detail_unknown_id_404(admin_client):
    import uuid

    assert admin_client.get(f"{LIST}/{uuid.uuid4()}").status_code == 404


# ── security ──────────────────────────────────────────────────────────────────
def test_merchant_token_cannot_list_merchants(api_client, merchant):
    """A merchant JWT must NOT reach the cross-tenant admin directory."""
    staff = factories.StaffUserFactory(merchant=merchant)
    token = str(RefreshToken.for_user(staff.user).access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert api_client.get(LIST).status_code in (401, 403)


def test_anonymous_cannot_list(api_client):
    assert api_client.get(LIST).status_code == 401
