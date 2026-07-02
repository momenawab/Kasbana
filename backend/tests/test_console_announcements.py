"""Communications & announcements tests (Phase 10).

Covers the Super-admin/Marketing gate (Support 403 on writes), segment
resolution, audience preview, send (in-app deliveries + emails) with stats, the
scheduled-send Celery task, the immutability of a sent announcement, and the
merchant-facing in-app list + mark-read (open stat).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from billing.services import subscription_for
from console.auth import issue_admin_tokens
from console.enums import AdminRole
from console.models import AdminAuditLog, AdminUser, Announcement, AnnouncementDelivery
from console.tasks import send_due_announcements
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db

BASE = "/api/admin/v1/announcements"


@pytest.fixture
def super_admin():
    a = AdminUser(email="super@stampn.net", role=AdminRole.SUPER_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def marketing_admin():
    a = AdminUser(email="mkt@stampn.net", role=AdminRole.MARKETING_ADMIN)
    a.set_password("supersecret1")
    a.save()
    return a


@pytest.fixture
def support_admin():
    a = AdminUser(email="support@stampn.net", role=AdminRole.SUPPORT)
    a.set_password("supersecret1")
    a.save()
    return a


def _admin(admin):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_admin_tokens(admin)['access']}")
    return c


def _merchant_with_owner(name="Shop", email="owner@shop.com"):
    m = factories.MerchantFactory(name=name)
    user = factories.UserFactory(email=email)
    factories.StaffUserFactory(merchant=m, user=user, role=Role.OWNER)
    return m


def _create(client, **over):
    payload = {"title": "Hi", "body": "News", "channel": "in_app", "audience": "all", **over}
    return client.post(BASE, payload, format="json")


# ── role gate ──────────────────────────────────────────────────────────────────
def test_support_cannot_create(api_client, support_admin):
    assert _create(_admin(support_admin)).status_code == 403


def test_marketing_can_create(api_client, marketing_admin):
    assert _create(_admin(marketing_admin)).status_code == 201


def test_any_admin_can_list(api_client, support_admin, marketing_admin):
    _create(_admin(marketing_admin))
    assert _admin(support_admin).get(BASE).status_code == 200


def test_unauthenticated_rejected(api_client):
    assert api_client.get(BASE).status_code == 401


# ── segments + preview ──────────────────────────────────────────────────────────
def test_audience_preview_by_plan(api_client, marketing_admin):
    m = _merchant_with_owner()
    sub = subscription_for(m)
    sub.plan = PlanTier.GROWTH
    sub.save()
    _merchant_with_owner("Other", "o2@shop.com")  # default plan, not GROWTH

    resp = _admin(marketing_admin).get(
        f"{BASE}/audience-preview", {"audience": "plan", "param": "GROWTH"}
    )
    assert resp.status_code == 200
    assert resp.json()["recipients"] == 1


def test_audience_preview_all(api_client, marketing_admin):
    _merchant_with_owner()
    _merchant_with_owner("Two", "o2@shop.com")
    resp = _admin(marketing_admin).get(f"{BASE}/audience-preview", {"audience": "all"})
    assert resp.json()["recipients"] == 2


# ── send (in-app + email) + stats ───────────────────────────────────────────────
def test_send_in_app_creates_deliveries(api_client, marketing_admin):
    _merchant_with_owner()
    _merchant_with_owner("Two", "o2@shop.com")
    ann_id = _create(_admin(marketing_admin), channel="in_app", audience="all").json()["id"]

    resp = _admin(marketing_admin).post(f"{BASE}/{ann_id}/send")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["recipients"] == 2
    assert body["stats"]["delivered"] == 2
    assert AnnouncementDelivery.objects.filter(announcement_id=ann_id).count() == 2
    assert AdminAuditLog.objects.filter(action="announcement.send").exists()


def test_send_email_uses_mail_backend(api_client, marketing_admin, mailoutbox):
    _merchant_with_owner(email="a@b.c")
    ann_id = _create(_admin(marketing_admin), channel="email", audience="all").json()["id"]

    body = _admin(marketing_admin).post(f"{BASE}/{ann_id}/send").json()
    assert body["emails_sent"] == 1
    assert len(mailoutbox) == 1
    assert "a@b.c" in mailoutbox[0].to
    # Email-only → no in-app delivery rows.
    assert AnnouncementDelivery.objects.filter(announcement_id=ann_id).count() == 0


def test_send_is_not_repeated(api_client, marketing_admin):
    _merchant_with_owner()
    ann_id = _create(_admin(marketing_admin)).json()["id"]
    _admin(marketing_admin).post(f"{BASE}/{ann_id}/send")
    resp = _admin(marketing_admin).post(f"{BASE}/{ann_id}/send")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ANNOUNCEMENT_SENT"


def test_sent_announcement_is_immutable(api_client, marketing_admin):
    _merchant_with_owner()
    ann_id = _create(_admin(marketing_admin)).json()["id"]
    _admin(marketing_admin).post(f"{BASE}/{ann_id}/send")
    resp = _admin(marketing_admin).patch(f"{BASE}/{ann_id}", {"title": "Edited"}, format="json")
    assert resp.status_code == 409


# ── scheduling ───────────────────────────────────────────────────────────────────
def test_schedule_then_beat_task_sends_due(api_client, marketing_admin):
    _merchant_with_owner()
    future = (timezone.now() + timedelta(hours=1)).isoformat()
    ann_id = _create(_admin(marketing_admin), schedule_at=future).json()["id"]

    resp = _admin(marketing_admin).post(f"{BASE}/{ann_id}/schedule")
    assert resp.status_code == 200
    assert resp.json()["status"] == "scheduled"

    # Not due yet.
    assert send_due_announcements() == 0

    # Move its send time into the past → the beat task delivers it.
    Announcement.objects.filter(id=ann_id).update(schedule_at=timezone.now() - timedelta(minutes=1))
    assert send_due_announcements() == 1
    assert Announcement.objects.get(id=ann_id).status == Announcement.Status.SENT


def test_schedule_requires_future_time(api_client, marketing_admin):
    _merchant_with_owner()
    ann_id = _create(_admin(marketing_admin)).json()["id"]  # no schedule_at
    resp = _admin(marketing_admin).post(f"{BASE}/{ann_id}/schedule")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SCHEDULE"


# ── merchant-facing in-app delivery ──────────────────────────────────────────────
def test_merchant_sees_and_reads_announcement(auth_client, api_client, marketing_admin, merchant):
    # merchant (the auth_client's merchant) needs an owner email for the segment.
    factories.StaffUserFactory(merchant=merchant, role=Role.OWNER)
    ann_id = _create(_admin(marketing_admin), channel="in_app", audience="all").json()["id"]
    _admin(marketing_admin).post(f"{BASE}/{ann_id}/send")

    listed = auth_client.get("/api/v1/announcements")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["read"] is False
    delivery_id = rows[0]["id"]

    read = auth_client.post(f"/api/v1/announcements/{delivery_id}/read")
    assert read.status_code == 200

    # Open reflected in admin stats.
    stats = _admin(marketing_admin).get(f"{BASE}/{ann_id}").json()["stats"]
    assert stats["opened"] == 1
    assert stats["open_rate"] == pytest.approx(1.0)


def test_merchant_cannot_read_another_merchants_delivery(auth_client, marketing_admin):
    other = _merchant_with_owner("Other", "o@x.com")
    ann = Announcement.objects.create(title="t", body="b", created_by=marketing_admin)
    delivery = AnnouncementDelivery.objects.create(announcement=ann, merchant=other)
    # auth_client is a different merchant → 404 (scoped lookup).
    assert auth_client.post(f"/api/v1/announcements/{delivery.id}/read").status_code == 404
