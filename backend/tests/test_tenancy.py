"""Tests for tenant isolation (contract exit criteria §4 Phase 1.0)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.http import Http404

from core.models import CustomerCard
from core.tenancy import get_scoped
from tests import factories

pytestmark = pytest.mark.django_db


def test_for_merchant_scopes_queryset():
    a = factories.MerchantFactory()
    b = factories.MerchantFactory()
    cc = factories.CustomerCardFactory(card=factories.CardFactory(merchant=a), merchant=a)

    assert CustomerCard.objects.for_merchant(a).filter(pk=cc.pk).exists()
    assert not CustomerCard.objects.for_merchant(b).filter(pk=cc.pk).exists()


def _request_for(merchant):
    return SimpleNamespace(staff=SimpleNamespace(merchant=merchant))


def test_get_scoped_returns_own_object():
    a = factories.MerchantFactory()
    cc = factories.CustomerCardFactory(card=factories.CardFactory(merchant=a), merchant=a)
    fetched = get_scoped(CustomerCard, _request_for(a), pk=cc.pk)
    assert fetched.pk == cc.pk


def test_get_scoped_cross_tenant_raises_404():
    a = factories.MerchantFactory()
    b = factories.MerchantFactory()
    cc = factories.CustomerCardFactory(card=factories.CardFactory(merchant=a), merchant=a)
    with pytest.raises(Http404):
        get_scoped(CustomerCard, _request_for(b), pk=cc.pk)
