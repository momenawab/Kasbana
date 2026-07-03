"""Platform Operations, Health & Config tests (Phase 14).

Covers OPS_MANAGE gating (Engineering + super, nobody else), the flag resolver
+ per-merchant override, settings, maintenance mode + its middleware enforcement,
the task monitor + retry, webhook replay, and wallet re-provision.
"""

from __future__ import annotations

import uuid

import pytest
from django.core.cache import cache
from django_celery_results.models import TaskResult

from billing.models import WebhookDelivery
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.flags import flag_enabled
from console.models import AdminUser, PlatformSetting
from tests.factories import CustomerCardFactory, MerchantFactory
from wallets.models import WalletSyncFailure

pytestmark = pytest.mark.django_db

OPS = "/api/admin/v1/ops"


def _admin(email, role):
    a = AdminUser(email=email, name=email.split("@")[0], role=role, is_active=True)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def eng_admin():
    return _admin("eng@stampn.net", AdminRole.ENGINEERING)


@pytest.fixture
def readonly_admin():
    return _admin("readonly@stampn.net", AdminRole.READ_ONLY)


@pytest.fixture
def super_admin():
    return _admin("super@stampn.net", AdminRole.SUPER_ADMIN)


def _bearer(client, admin):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return client


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# ── health ───────────────────────────────────────────────────────────────────
def test_health_any_admin(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).get(f"{OPS}/health")
    assert resp.status_code == 200
    assert resp.data["database"]["ok"] is True
    assert resp.data["cache"]["ok"] is True
    assert resp.data["healthy"] is True
    assert "celery" in resp.data and "queues" in resp.data


# ── feature flags ──────────────────────────────────────────────────────────────
def test_engineering_can_create_and_toggle_flag(api_client, eng_admin):
    client = _bearer(api_client, eng_admin)
    resp = client.post(
        f"{OPS}/flags",
        {"key": "beta_x", "label": "Beta X", "enabled": False},
        format="json",
    )
    assert resp.status_code == 201
    assert flag_enabled("beta_x") is False
    resp = client.patch(f"{OPS}/flags/beta_x", {"enabled": True}, format="json")
    assert resp.status_code == 200
    assert flag_enabled("beta_x") is True


def test_readonly_cannot_manage_flags(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).post(
        f"{OPS}/flags", {"key": "x", "enabled": True}, format="json"
    )
    assert resp.status_code == 403
    # but can read
    assert _bearer(api_client, readonly_admin).get(f"{OPS}/flags").status_code == 200


def test_duplicate_flag_key_conflicts(api_client, eng_admin):
    client = _bearer(api_client, eng_admin)
    client.post(f"{OPS}/flags", {"key": "dup", "enabled": True}, format="json")
    resp = client.post(f"{OPS}/flags", {"key": "dup", "enabled": False}, format="json")
    assert resp.status_code == 409


def test_per_merchant_override_wins(api_client, eng_admin):
    client = _bearer(api_client, eng_admin)
    merchant = MerchantFactory()
    client.post(f"{OPS}/flags", {"key": "wa", "enabled": False}, format="json")
    # global off, override this merchant on
    resp = client.post(
        f"{OPS}/flags/wa/override",
        {"merchant_id": str(merchant.id), "enabled": True},
        format="json",
    )
    assert resp.status_code == 200
    assert flag_enabled("wa") is False  # global default
    assert flag_enabled("wa", merchant=merchant) is True  # override wins
    # clear it → falls back to global
    resp = client.delete(
        f"{OPS}/flags/wa/override", {"merchant_id": str(merchant.id)}, format="json"
    )
    assert resp.status_code == 200
    assert flag_enabled("wa", merchant=merchant) is False


def test_unknown_flag_defaults_off():
    assert flag_enabled("does_not_exist") is False


# ── settings ───────────────────────────────────────────────────────────────────
def test_engineering_can_upsert_setting(api_client, eng_admin):
    resp = _bearer(api_client, eng_admin).patch(
        f"{OPS}/settings/support_email",
        {"value": {"address": "help@stampn.net"}, "description": "Support inbox"},
        format="json",
    )
    assert resp.status_code == 200
    assert PlatformSetting.objects.get(key="support_email").value == {"address": "help@stampn.net"}


def test_readonly_cannot_write_setting(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).patch(
        f"{OPS}/settings/x", {"value": {}}, format="json"
    )
    assert resp.status_code == 403


# ── maintenance mode + middleware ───────────────────────────────────────────────
def test_maintenance_toggle_blocks_merchant_api(api_client, eng_admin):
    client = _bearer(api_client, eng_admin)
    # off by default
    assert client.get(f"{OPS}/maintenance").data["enabled"] is False

    resp = client.patch(
        f"{OPS}/maintenance", {"enabled": True, "message": "Back soon"}, format="json"
    )
    assert resp.status_code == 200 and resp.data["enabled"] is True

    # merchant-facing API is now 503'd by the middleware…
    blocked = api_client.get("/api/v1/anything")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "MAINTENANCE"
    # …but the admin console stays reachable so we can turn it back off.
    assert _bearer(api_client, eng_admin).get(f"{OPS}/health").status_code == 200

    _bearer(api_client, eng_admin).patch(f"{OPS}/maintenance", {"enabled": False}, format="json")
    assert api_client.get("/api/health/").status_code == 200


def test_readonly_cannot_toggle_maintenance(api_client, readonly_admin):
    resp = _bearer(api_client, readonly_admin).patch(
        f"{OPS}/maintenance", {"enabled": True}, format="json"
    )
    assert resp.status_code == 403


# ── task monitor + retry ─────────────────────────────────────────────────────
def _task(status="FAILURE", args="('abc',)", name="wallets.tasks.sync_google_class"):
    return TaskResult.objects.create(
        task_id=str(uuid.uuid4()), task_name=name, status=status, task_args=args
    )


def test_task_list_filters_by_status(api_client, eng_admin):
    _task(status="FAILURE")
    _task(status="SUCCESS")
    resp = _bearer(api_client, eng_admin).get(f"{OPS}/tasks", {"status": "FAILURE"})
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["status"] == "FAILURE"


def test_task_retry_reenqueues(api_client, eng_admin, monkeypatch):
    # send_task always publishes to the broker (eager is ignored), so stub it.
    class _Res:
        id = "new-task-123"

    monkeypatch.setattr("config.celery.app.send_task", lambda *a, **k: _Res())
    t = _task(name="wallets.tasks.sync_google_class", args=f"('{uuid.uuid4()}',)")
    resp = _bearer(api_client, eng_admin).post(f"{OPS}/tasks/{t.task_id}/retry")
    assert resp.status_code == 200
    assert resp.data["retried"] is True
    assert resp.data["new_task_id"] == "new-task-123"


def test_task_retry_rejects_unparseable_args(api_client, eng_admin):
    t = _task(args="not a literal (")
    resp = _bearer(api_client, eng_admin).post(f"{OPS}/tasks/{t.task_id}/retry")
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "UNPARSEABLE_ARGS"


def test_readonly_cannot_retry(api_client, readonly_admin):
    t = _task()
    resp = _bearer(api_client, readonly_admin).post(f"{OPS}/tasks/{t.task_id}/retry")
    assert resp.status_code == 403


# ── webhook deliveries + replay ────────────────────────────────────────────────
def test_webhook_list_and_replay_no_merchant(api_client, eng_admin):
    client = _bearer(api_client, eng_admin)
    delivery = WebhookDelivery.objects.create(
        provider="paymob",
        kind="success",
        gateway_ref="ref-1",
        status=WebhookDelivery.Status.FAILED,
        payload={
            "provider": "paymob",
            "kind": "success",
            "gateway_ref": "ref-1",
            "merchant_id": str(uuid.uuid4()),
            "plan": None,
            "amount_egp": None,
        },
    )
    assert client.get(f"{OPS}/webhooks", {"provider": "paymob"}).status_code == 200

    resp = client.post(f"{OPS}/webhooks/{delivery.id}/replay")
    assert resp.status_code == 200
    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.NO_MERCHANT  # unknown merchant
    assert delivery.processed_at is not None


def test_webhook_replay_empty_payload_conflicts(api_client, eng_admin):
    d = WebhookDelivery.objects.create(
        provider="paymob", status=WebhookDelivery.Status.INVALID, payload={}
    )
    resp = _bearer(api_client, eng_admin).post(f"{OPS}/webhooks/{d.id}/replay")
    assert resp.status_code == 409


def test_readonly_cannot_replay(api_client, readonly_admin):
    d = WebhookDelivery.objects.create(
        provider="paymob", status=WebhookDelivery.Status.FAILED, payload={"x": 1}
    )
    resp = _bearer(api_client, readonly_admin).post(f"{OPS}/webhooks/{d.id}/replay")
    assert resp.status_code == 403


# ── wallet sync failures + reprovision ───────────────────────────────────────
def test_wallet_failure_list_and_reprovision(api_client, eng_admin, monkeypatch):
    monkeypatch.setattr("wallets.tasks.provision_pass.delay", lambda *a, **k: None)
    cc = CustomerCardFactory()
    failure = WalletSyncFailure.objects.create(
        customer_card=cc,
        merchant=cc.merchant,
        platform="GOOGLE",
        operation="provision",
        error="boom",
    )
    client = _bearer(api_client, eng_admin)
    assert client.get(f"{OPS}/wallet-failures", {"resolved": "false"}).status_code == 200

    resp = client.post(f"{OPS}/wallet-failures/{failure.id}/reprovision")
    assert resp.status_code == 200
    failure.refresh_from_db()
    assert failure.resolved is True and failure.resolved_at is not None


def test_reprovision_gone_card_conflicts(api_client, eng_admin, monkeypatch):
    monkeypatch.setattr("wallets.tasks.provision_pass.delay", lambda *a, **k: None)
    merchant = MerchantFactory()
    failure = WalletSyncFailure.objects.create(
        customer_card=None, merchant=merchant, operation="provision", error="x"
    )
    resp = _bearer(api_client, eng_admin).post(f"{OPS}/wallet-failures/{failure.id}/reprovision")
    assert resp.status_code == 409
    assert resp.data["error"]["code"] == "CARD_GONE"


def test_readonly_cannot_reprovision(api_client, readonly_admin):
    merchant = MerchantFactory()
    failure = WalletSyncFailure.objects.create(
        customer_card=None, merchant=merchant, operation="provision"
    )
    resp = _bearer(api_client, readonly_admin).post(
        f"{OPS}/wallet-failures/{failure.id}/reprovision"
    )
    assert resp.status_code == 403
