"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from tests import factories


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
def no_cooldown(monkeypatch):
    """Disable the inter-stamp cooldown so balance math can be exercised."""
    from core import constants

    monkeypatch.setattr(constants, "STAMP_COOLDOWN_SECONDS", 0)
