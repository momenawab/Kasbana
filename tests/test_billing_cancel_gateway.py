"""Cancellation actually stops the money (Paymob plan §7 / §11.6).

Before this, cancelling only flipped a local flag — Paymob kept deducting. The
interesting cases here are the failures: a merchant who believes they cancelled
but is still being charged is the worst outcome in billing, and it is invisible
until a chargeback.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from billing import services
from billing.models import Subscription
from billing.plans import BillingStatus
from billing.tasks import expire_scheduled_cancellations, retry_pending_gateway_cancels
from core.enums import PlanTier

pytestmark = pytest.mark.django_db


class FakeGateway:
    """Records the subscription actions billing asks for."""

    provider = "paymob"

    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def _act(self, action, subscription_id):
        if self.fail:
            raise RuntimeError("paymob is down")
        self.calls.append((action, subscription_id))
        return {"id": subscription_id, "state": action}

    def suspend_subscription(self, subscription_id: str):
        return self._act("suspend", subscription_id)

    def resume_subscription(self, subscription_id: str):
        return self._act("resume", subscription_id)

    def cancel_subscription(self, subscription_id: str):
        return self._act("cancel", subscription_id)


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr("billing.gateways.get_gateway", lambda provider="paymob": fake)
    return fake


@pytest.fixture
def broken_gateway(monkeypatch):
    fake = FakeGateway(fail=True)
    monkeypatch.setattr("billing.gateways.get_gateway", lambda provider="paymob": fake)
    return fake


def _subscribed(merchant, **kwargs) -> Subscription:
    sub = services.subscription_for(merchant)
    sub.provider = "paymob"
    sub.paymob_subscription_id = "1264"
    sub.plan = PlanTier.GROWTH
    sub.status = BillingStatus.ACTIVE
    sub.current_period_end = timezone.now() + timedelta(days=20)
    for k, v in kwargs.items():
        setattr(sub, k, v)
    sub.save()
    return sub


# ── Cancel stops the next deduction ─────────────────────────────────────────
def test_cancel_suspends_on_paymob(merchant, gateway):
    _subscribed(merchant)

    services.schedule_cancel(merchant)

    # Suspend, not cancel: the merchant keeps the period they paid for and may
    # still change their mind.
    assert gateway.calls == [("suspend", "1264")]


def test_cancel_keeps_access_until_the_period_ends(merchant, gateway):
    _subscribed(merchant)

    sub = services.schedule_cancel(merchant)

    assert sub.status == BillingStatus.ACTIVE
    assert sub.effective_plan() == PlanTier.GROWTH
    assert sub.cancels_on() is not None


def test_the_local_flag_is_committed_before_paymob_is_told(merchant, monkeypatch):
    """Paymob echoes our suspend back as a "suspended" callback, and the webhook
    reads cancel_at_period_end to tell our own request from a bank block. If the
    echo could arrive first, the handler would mark them PAST_DUE."""
    seen: dict[str, bool] = {}

    class CheckingGateway(FakeGateway):
        def suspend_subscription(self, subscription_id):
            # What a concurrent webhook would read at this moment.
            seen["flag"] = Subscription.objects.get(
                paymob_subscription_id=subscription_id
            ).cancel_at_period_end
            return super().suspend_subscription(subscription_id)

    monkeypatch.setattr("billing.gateways.get_gateway", lambda provider="paymob": CheckingGateway())
    _subscribed(merchant)

    services.schedule_cancel(merchant)

    assert seen["flag"] is True


def test_an_immediate_cancel_closes_rather_than_suspends(merchant, gateway):
    """No period left to protect, so don't leave a suspended sub on Paymob."""
    _subscribed(merchant, current_period_end=None)

    sub = services.schedule_cancel(merchant)

    assert sub.status == BillingStatus.CANCELED
    assert gateway.calls == [("cancel", "1264")]


def test_cancelling_during_the_trial_stops_the_day_14_charge(merchant, gateway):
    """§11.6: the trial auto-converts, so cancelling must reach Paymob or they
    get charged the full plan price at day 14."""
    _subscribed(
        merchant,
        status=BillingStatus.TRIALING,
        current_period_end=None,
        trial_ends_at=timezone.now() + timedelta(days=9),
    )

    services.schedule_cancel(merchant)

    assert gateway.calls == [("suspend", "1264")]
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.cancel_at_period_end is True
    assert sub.effective_plan() == PlanTier.GROWTH  # access until trial end


def test_a_trial_with_no_linked_card_needs_no_gateway_call(merchant, gateway):
    _subscribed(merchant, status=BillingStatus.TRIALING, paymob_subscription_id="")

    services.schedule_cancel(merchant)

    assert gateway.calls == []
    # Nothing can bill them, so this is "stopped" — not a failure to retry.
    assert Subscription.objects.get(merchant=merchant).gateway_billing_stopped is True


# ── Gateway failure must not strand the merchant ────────────────────────────
def test_a_gateway_failure_still_cancels_locally(merchant, broken_gateway):
    """Refusing to cancel because a third party is unreachable would be worse
    than a retryable failure."""
    _subscribed(merchant)

    sub = services.schedule_cancel(merchant)

    assert sub.cancel_at_period_end is True
    assert Subscription.objects.get(merchant=merchant).gateway_billing_stopped is False


def test_a_failed_suspend_is_retried_by_the_sweep(merchant, monkeypatch):
    _subscribed(merchant)
    monkeypatch.setattr(
        "billing.gateways.get_gateway", lambda provider="paymob": FakeGateway(fail=True)
    )
    services.schedule_cancel(merchant)
    assert Subscription.objects.get(merchant=merchant).gateway_billing_stopped is False

    # Paymob comes back.
    working = FakeGateway()
    monkeypatch.setattr("billing.gateways.get_gateway", lambda provider="paymob": working)

    assert retry_pending_gateway_cancels() == 1

    assert working.calls == [("suspend", "1264")]
    assert Subscription.objects.get(merchant=merchant).gateway_billing_stopped is True


def test_the_sweep_leaves_alone_the_cancels_that_landed(merchant, gateway):
    """Otherwise every pending cancel is re-suspended hourly until its period
    ends — thousands of pointless calls."""
    _subscribed(merchant)
    services.schedule_cancel(merchant)
    gateway.calls.clear()

    assert retry_pending_gateway_cancels() == 0
    assert gateway.calls == []


def test_the_sweep_ignores_subscriptions_that_are_not_cancelling(merchant, gateway):
    _subscribed(merchant, cancel_at_period_end=False)

    assert retry_pending_gateway_cancels() == 0
    assert gateway.calls == []


# ── Period end closes the subscription for good ─────────────────────────────
def test_period_end_cancels_the_subscription_on_paymob(merchant, gateway):
    _subscribed(
        merchant,
        cancel_at_period_end=True,
        current_period_end=timezone.now() - timedelta(hours=1),
    )

    assert expire_scheduled_cancellations() == 1

    assert gateway.calls == [("cancel", "1264")]
    sub = Subscription.objects.get(merchant=merchant)
    assert sub.status == BillingStatus.CANCELED
    assert sub.effective_plan() is None


def test_period_end_still_closes_locally_when_paymob_is_down(merchant, broken_gateway):
    """The period is over either way — access must not hinge on reachability."""
    _subscribed(
        merchant,
        cancel_at_period_end=True,
        current_period_end=timezone.now() - timedelta(hours=1),
    )

    assert expire_scheduled_cancellations() == 1

    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.CANCELED


def test_one_merchants_gateway_failure_does_not_block_the_others(merchant, monkeypatch):
    """A bulk update would have been atomic; iterating must not be all-or-nothing."""
    from tests import factories

    others = [factories.MerchantFactory() for _ in range(2)]
    lapsed = timezone.now() - timedelta(hours=1)
    for i, m in enumerate([merchant, *others]):
        _subscribed(m, cancel_at_period_end=True, current_period_end=lapsed)
        Subscription.objects.filter(merchant=m).update(paymob_subscription_id=f"sub-{i}")

    class FlakyGateway(FakeGateway):
        def cancel_subscription(self, subscription_id):
            if subscription_id == "sub-1":
                raise RuntimeError("paymob is down for this one")
            return super().cancel_subscription(subscription_id)

    flaky = FlakyGateway()
    monkeypatch.setattr("billing.gateways.get_gateway", lambda provider="paymob": flaky)

    assert expire_scheduled_cancellations() == 3

    assert sorted(c[1] for c in flaky.calls) == ["sub-0", "sub-2"]
    # All three are closed locally regardless.
    assert Subscription.objects.filter(status=BillingStatus.CANCELED).count() == 3


def test_period_end_does_not_touch_a_sub_still_inside_its_period(merchant, gateway):
    _subscribed(merchant, cancel_at_period_end=True)  # ends in 20 days

    assert expire_scheduled_cancellations() == 0

    assert gateway.calls == []
    assert Subscription.objects.get(merchant=merchant).status == BillingStatus.ACTIVE


# ── Re-subscribing ──────────────────────────────────────────────────────────
def test_resubscribing_clears_the_stopped_flag(merchant, gateway):
    """Otherwise the sweep would suspend a merchant who is paying again."""
    _subscribed(merchant)
    services.schedule_cancel(merchant)
    assert Subscription.objects.get(merchant=merchant).gateway_billing_stopped is True

    services.activate_plan(merchant, PlanTier.GROWTH, provider="paymob", gateway_ref="o1")

    sub = Subscription.objects.get(merchant=merchant)
    assert sub.gateway_billing_stopped is False
    assert sub.cancel_at_period_end is False
    gateway.calls.clear()
    assert retry_pending_gateway_cancels() == 0
    assert gateway.calls == []
