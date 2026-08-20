"""The recurring-subscription webhook: trigger_type → subscription state.

This is the path that makes billing actually recur, and the one that can revoke
a paying merchant's access, so the state transitions are asserted directly
rather than through the HTTP layer where a 200 hides everything.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_lib
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from billing import services
from billing.models import Invoice, InvoiceStatus, Subscription, WebhookDelivery
from billing.plans import BillingInterval, BillingStatus
from core.enums import PlanTier

pytestmark = pytest.mark.django_db

SECRET = "sub-hmac-secret"
URL = "/api/v1/billing/webhook/paymob/subscription"


@pytest.fixture(autouse=True)
def _paymob(settings):
    settings.BILLING = {"PAYMOB": {"HMAC_SECRET": SECRET}}
    settings.DEBUG = False


def _body(trigger_type, sub_id="1264", **data) -> dict:
    digest = hmac_lib.new(
        SECRET.encode(), f"{trigger_type}for{sub_id}".encode(), hashlib.sha512
    ).hexdigest()
    return {
        "subscription_data": {"id": sub_id, **data},
        "trigger_type": trigger_type,
        "hmac": digest,
    }


def _post(payload: dict):
    return APIClient().post(URL, data=json.dumps(payload), content_type="application/json")


def _subscribed(merchant, **kwargs) -> Subscription:
    sub = services.subscription_for(merchant)
    sub.provider = "paymob"
    sub.paymob_subscription_id = "1264"
    sub.plan = PlanTier.GROWTH
    for k, v in kwargs.items():
        setattr(sub, k, v)
    sub.save()
    return sub


# ── Renewal ─────────────────────────────────────────────────────────────────
def test_successful_renewal_books_an_invoice_and_extends_the_period(merchant):
    _subscribed(merchant, status=BillingStatus.TRIALING)

    resp = _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15"))
    assert resp.status_code == 200

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert timezone.localtime(sub.current_period_end).date().isoformat() == "2026-08-15"
    invoice = Invoice.objects.get(merchant=merchant)
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_egp == Decimal("999")


def test_renewal_trusts_paymobs_next_billing_over_our_arithmetic(merchant):
    """Paymob decides when it deducts next; a retrial or suspension shifts the
    cycle, and a locally computed +30d would silently drift from reality."""
    _subscribed(merchant, billing_interval=BillingInterval.MONTHLY)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2027-01-09"))

    sub = Subscription.objects.get(merchant=merchant)
    assert timezone.localtime(sub.current_period_end).date().isoformat() == "2027-01-09"


def test_access_lasts_through_the_whole_billing_day(merchant):
    """A date-only next_billing must not mean midnight: Paymob charges at some
    hour on that date, and locking at 00:00 would cut off a paying merchant
    before the charge they're waiting for."""
    _subscribed(merchant, status=BillingStatus.ACTIVE, cancel_at_period_end=True)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15"))

    sub = Subscription.objects.get(merchant=merchant)
    local = timezone.localtime(sub.current_period_end)
    assert local.date().isoformat() == "2026-08-15"
    assert (local.hour, local.minute) == (23, 59)


def test_a_next_billing_with_a_time_is_honoured_as_given(merchant):
    """Paymob sends a date today, but its own callback sample shows ISO
    timestamps elsewhere — a timestamp must not get rounded up to end-of-day."""
    _subscribed(merchant)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15T09:30:00"))

    local = timezone.localtime(Subscription.objects.get(merchant=merchant).current_period_end)
    assert (local.hour, local.minute) == (9, 30)


def test_an_unparseable_next_billing_falls_back_instead_of_crashing(merchant):
    _subscribed(merchant, billing_interval=BillingInterval.MONTHLY)

    resp = _post(_body("Successful Transaction", amount_cents=99900, next_billing="soon"))

    assert resp.status_code == 200
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert sub.current_period_end > timezone.now() + timedelta(days=29)


def test_renewal_without_next_billing_falls_back_to_the_interval(merchant):
    _subscribed(merchant, billing_interval=BillingInterval.ANNUAL)

    _post(_body("Successful Transaction", amount_cents=999000))

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.current_period_end > timezone.now() + timedelta(days=359)


def test_replayed_renewal_does_not_double_invoice(merchant):
    _subscribed(merchant)
    payload = _body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15")

    _post(payload)
    _post(payload)

    assert Invoice.objects.filter(merchant=merchant).count() == 1


def test_next_cycle_books_its_own_invoice(merchant):
    """Two different cycles must not collapse into one invoice just because the
    callback carries no transaction id of its own."""
    _subscribed(merchant)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15"))
    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-09-15"))

    assert Invoice.objects.filter(merchant=merchant, status=InvoiceStatus.PAID).count() == 2


def test_trial_converts_to_the_selected_plan(merchant):
    """Day-14 auto-charge: the merchant lands on the tier they picked."""
    _subscribed(merchant, status=BillingStatus.TRIALING, plan=PlanTier.STARTER)

    _post(_body("Successful Transaction", amount_cents=59900, next_billing="2026-08-15"))

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert sub.effective_plan() == PlanTier.STARTER
    merchant.refresh_from_db()
    assert merchant.plan == PlanTier.STARTER  # mirrored for cheap reads


def test_renewal_does_not_silently_undo_a_pending_cancel(merchant):
    """If a cancel is pending and Paymob charges anyway (a suspend that didn't
    take), clearing the flag would bill them again next cycle."""
    _subscribed(merchant, status=BillingStatus.ACTIVE, cancel_at_period_end=True)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15"))

    assert Subscription.objects.get(merchant=merchant).cancel_at_period_end is True


# ── Failure → dunning ───────────────────────────────────────────────────────
def test_failed_transaction_marks_past_due(merchant):
    """PAST_DUE was unreachable before this webhook existed."""
    _subscribed(merchant, status=BillingStatus.ACTIVE)

    _post(_body("Failed Transaction", amount_cents=99900, next_billing="2026-08-15"))

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.PAST_DUE
    assert Invoice.objects.get(merchant=merchant).status == InvoiceStatus.FAILED


def test_failed_overdue_locks_after_paymob_gave_up_retrying(merchant):
    _subscribed(merchant, status=BillingStatus.PAST_DUE)

    _post(_body("Failed Overdue Transaction", amount_cents=99900, next_billing="2026-08-15"))

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.LOCKED
    assert sub.effective_plan() is None  # access revoked, data retained


def test_repeated_failures_in_one_cycle_book_one_invoice(merchant):
    _subscribed(merchant, status=BillingStatus.ACTIVE)
    payload = _body("Failed Transaction", amount_cents=99900, next_billing="2026-08-15")

    _post(payload)
    _post(payload)

    assert Invoice.objects.filter(merchant=merchant).count() == 1


# ── Suspend / cancel reconciliation ─────────────────────────────────────────
def test_our_own_cancel_echo_does_not_revoke_access_early(merchant):
    """We suspend on Paymob the moment a merchant asks to cancel; acting on the
    echo would lock them out immediately instead of at period end."""
    end = timezone.now() + timedelta(days=20)
    _subscribed(
        merchant,
        status=BillingStatus.ACTIVE,
        cancel_at_period_end=True,
        current_period_end=end,
    )

    _post(_body("suspended"))

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.ACTIVE
    assert sub.effective_plan() == PlanTier.GROWTH  # still paid up


def test_suspension_we_did_not_ask_for_marks_past_due(merchant):
    """e.g. the customer's bank blocked the card."""
    _subscribed(merchant, status=BillingStatus.ACTIVE, cancel_at_period_end=False)

    _post(_body("suspended"))

    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.PAST_DUE


def test_cancellation_we_did_not_ask_for_is_reconciled(merchant):
    _subscribed(merchant, status=BillingStatus.ACTIVE, cancel_at_period_end=False)

    _post(_body("canceled"))

    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.CANCELED


# ── No-op + unknown triggers ────────────────────────────────────────────────
@pytest.mark.parametrize(
    "trigger",
    ["Subscription Created", "resumed", "updated", "register_webhook", "add_secondry_card"],
)
def test_lifecycle_noise_changes_nothing(merchant, trigger):
    _subscribed(merchant, status=BillingStatus.ACTIVE)

    assert _post(_body(trigger)).status_code == 200

    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.ACTIVE
    assert not Invoice.objects.filter(merchant=merchant).exists()


def test_an_unknown_trigger_is_acked_not_500ed(merchant):
    """Paymob can extend the catalogue without telling us; a crash here would
    make them retry forever."""
    _subscribed(merchant, status=BillingStatus.ACTIVE)

    assert _post(_body("some_future_trigger")).status_code == 200
    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.ACTIVE


# ── Security + unmatched ────────────────────────────────────────────────────
def test_a_forged_callback_is_rejected_and_changes_nothing(merchant):
    _subscribed(merchant, status=BillingStatus.ACTIVE)
    payload = _body("canceled")
    payload["hmac"] = "0" * 128

    assert _post(payload).status_code == 400

    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.ACTIVE
    assert WebhookDelivery.objects.filter(status=WebhookDelivery.Status.INVALID).exists()


def test_an_unmatched_subscription_is_acked_and_logged(merchant):
    """Ack anyway — retries won't help — but keep the row so ops can see it."""
    _subscribed(merchant)

    resp = _post(_body("Successful Transaction", sub_id="9999", amount_cents=99900))

    assert resp.status_code == 200
    assert WebhookDelivery.objects.filter(status=WebhookDelivery.Status.NO_MERCHANT).exists()
    assert not Invoice.objects.filter(merchant=merchant).exists()


def test_a_processed_callback_is_logged_for_ops(merchant):
    _subscribed(merchant)

    _post(_body("Successful Transaction", amount_cents=99900, next_billing="2026-08-15"))

    row = WebhookDelivery.objects.get(status=WebhookDelivery.Status.PROCESSED)
    assert row.kind == "sub:success"
    assert row.gateway_ref == "1264"
    # The verbatim trigger survives in the payload even though `kind` is short.
    assert row.payload["trigger_type"] == "Successful Transaction"
    assert row.payload["next_billing"] == "2026-08-15"
