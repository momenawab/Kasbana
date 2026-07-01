"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from tests import factories


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Reset rate-limit counters between tests so throttles (which key on the
    shared test-client IP) don't bleed across the suite."""
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def merchant():
    return factories.MerchantFactory()


@pytest.fixture
def card(merchant):
    return factories.CardFactory(merchant=merchant, stamps_required=5)


@pytest.fixture
def reward(card):
    return factories.RewardFactory(card=card, threshold=5)


@pytest.fixture
def customer_card(card):
    return factories.CustomerCardFactory(card=card, merchant=card.merchant)


@pytest.fixture
def staff_user(merchant):
    """An active staff member of ``merchant`` (Admin by factory default)."""
    return factories.StaffUserFactory(merchant=merchant)


@pytest.fixture
def auth_client(api_client, staff_user):
    """APIClient authenticated as ``staff_user`` via a SimpleJWT access token."""
    from rest_framework_simplejwt.tokens import RefreshToken

    access = RefreshToken.for_user(staff_user.user).access_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api_client


@pytest.fixture
def no_cooldown(monkeypatch):
    """Disable the inter-stamp cooldown so balance math can be exercised."""
    from core import constants

    monkeypatch.setattr(constants, "STAMP_COOLDOWN_SECONDS", 0)
