"""Tests for the customer CSV export endpoint (Phase 3).

Covers the ``export`` entitlement gate (402 when the plan lacks it), a small
end-to-end export (header + one row, filters honoured), and role enforcement.
"""

from __future__ import annotations

import csv
import io

import pytest

from billing import services
from core.enums import PlanTier, Role
from tests import factories

pytestmark = pytest.mark.django_db

EXPORT_URL = "/api/v1/customers/export"


def _read_csv(response) -> list[list[str]]:
    """Drain a StreamingHttpResponse into parsed CSV rows (utf-8-sig strips the
    leading BOM the export emits for Excel)."""
    body = b"".join(response.streaming_content).decode("utf-8-sig")
    return list(csv.reader(io.StringIO(body)))


def test_export_denied_without_entitlement(auth_client, merchant):
    # FREE plan has export=False -> the gate raises PlanLimit -> HTTP 402.
    services.activate_plan(merchant, PlanTier.FREE)
    resp = auth_client.get(EXPORT_URL)
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PLAN_LIMIT"


def test_export_returns_csv_on_trial(auth_client, merchant):
    # Default merchant is on a trial -> Growth-level, so export is allowed.
    card = factories.CardFactory(merchant=merchant, name="Coffee", stamps_required=8)
    factories.CustomerCardFactory(
        card=card,
        merchant=merchant,
        customer_name="Ali",
        customer_phone="+201000000001",
        stamp_count=3,
    )

    resp = auth_client.get(EXPORT_URL)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert "attachment" in resp["Content-Disposition"]
    assert resp["Content-Disposition"].endswith('.csv"')

    # streaming_content is single-pass: drain once, assert the BOM, then parse.
    raw = b"".join(resp.streaming_content)
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0] == [
        "customer_name",
        "customer_phone",
        "customer_email",
        "card_name",
        "stamp_count",
        "stamps_required",
        "status",
        "enrolled_at",
        "last_event_at",
    ]
    assert len(rows) == 2  # header + one customer
    body_row = rows[1]
    assert body_row[0] == "Ali"
    assert body_row[1] == "+201000000001"
    assert body_row[3] == "Coffee"  # card_name (index 3, after the email column)
    assert body_row[4] == "3"  # stamp_count
    assert body_row[5] == "8"  # stamps_required


def test_export_honours_search_filter(auth_client, merchant):
    card = factories.CardFactory(merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant, customer_name="Mona")
    factories.CustomerCardFactory(card=card, merchant=merchant, customer_name="Sara")

    resp = auth_client.get(EXPORT_URL, {"search": "Mona"})
    assert resp.status_code == 200
    rows = _read_csv(resp)
    assert len(rows) == 2  # header + only the matching customer
    assert rows[1][0] == "Mona"


def test_export_scoped_to_caller_merchant(auth_client, merchant):
    # A customer of another merchant must never appear in this export.
    card = factories.CardFactory(merchant=merchant)
    factories.CustomerCardFactory(card=card, merchant=merchant, customer_name="Mine")
    other = factories.MerchantFactory()
    other_card = factories.CardFactory(merchant=other)
    factories.CustomerCardFactory(card=other_card, merchant=other, customer_name="Theirs")

    rows = _read_csv(auth_client.get(EXPORT_URL))
    names = [r[0] for r in rows[1:]]
    assert names == ["Mine"]


def test_export_forbidden_for_scanner(merchant):
    # Scanner is outside the CanEngage role set (Owner/Admin/Marketing) -> 403,
    # short-circuiting before the entitlement gate.
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    staff = factories.StaffUserFactory(merchant=merchant, role=Role.SCANNER)
    client = APIClient()
    access = RefreshToken.for_user(staff.user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    resp = client.get(EXPORT_URL)
    assert resp.status_code == 403
