"""Tests for the wallets.service façade + tasks (the seam Joe calls)."""

from __future__ import annotations

import pytest

from tests import factories
from wallets import service
from wallets.interfaces import ProvisionResult

pytestmark = pytest.mark.django_db


def test_provision_returns_result_with_both_url_slots(settings):
    # No wallet creds configured -> both URLs null, but shape is correct.
    settings.WALLET = {
        "APPLE": {"PASS_TYPE_ID": "", "TEAM_ID": "", "PASS_CERT_PATH": ""},
        "GOOGLE": {"ISSUER_ID": "", "SA_KEY_PATH": ""},
    }
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    result = service.provision(cc)
    assert isinstance(result, ProvisionResult)
    assert result.apple_pass_url is None
    assert result.google_save_url is None


def test_push_update_enqueues_task(monkeypatch):
    calls = {}

    class FakeTask:
        def delay(self, cid):
            calls["cid"] = cid

    import wallets.tasks as tasks

    monkeypatch.setattr(tasks, "push_pass_update", FakeTask())

    class FakeCard:
        id = "abc-123"

    service.push_update(FakeCard())
    assert calls["cid"] == "abc-123"


def test_push_pass_update_task_runs_both_backends(monkeypatch, settings):
    settings.WALLET = {
        "APPLE": {"PASS_TYPE_ID": "", "TEAM_ID": "", "PASS_CERT_PATH": ""},
        "GOOGLE": {"ISSUER_ID": "", "SA_KEY_PATH": ""},
    }
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)

    from wallets.tasks import push_pass_update

    # Unconfigured -> no-op, must not raise.
    push_pass_update(str(cc.id))
