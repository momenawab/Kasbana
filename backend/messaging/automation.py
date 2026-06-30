"""Automation triggers (Phase 1.7).

Two firing paths feed the same ``dispatch``:

- **event-driven** — ``reward_ready`` (a stamp tips a card to its threshold) and
  ``welcome`` (enrollment) fire inline from ledger/enrollment hooks;
- **date-driven** — ``birthday`` / ``expiry`` / ``winback`` fire from the daily
  ``scan_automations`` beat.

``dispatch`` is best-effort: it respects the ``enabled`` flag, the WhatsApp
capability + quota (silently skipping when unavailable — a background trigger
never raises into a request), and the channel.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from billing import entitlements
from core.models import CustomerCard, Merchant
from messaging.enums import AutomationKey, MessageChannel
from messaging.models import Automation
from messaging.segments import LAPSED_DAYS

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES: dict[str, str] = {
    AutomationKey.REWARD_READY: "Your reward is ready — come redeem it!",
    AutomationKey.EXPIRY: "Your stamps are expiring soon. Visit us to keep them!",
    AutomationKey.BIRTHDAY: "Happy birthday! Enjoy a treat on us 🎉",
    AutomationKey.WINBACK: "We miss you! Here's a little something to bring you back.",
    AutomationKey.WELCOME: "Welcome! Thanks for joining our loyalty program.",
}


def _automation(merchant: Merchant, key: str) -> Automation | None:
    return Automation.objects.filter(merchant=merchant, key=key, enabled=True).first()


def dispatch(merchant: Merchant, customer: CustomerCard, key: str) -> bool:
    """Fire automation ``key`` for ``customer`` if enabled.

    PUSH rides the free wallet channel (no capability/quota gate); WhatsApp is
    gated by capability + monthly quota. ``BOTH`` does each independently.
    Returns ``True`` when at least one channel was dispatched.
    """
    automation = _automation(merchant, key)
    if automation is None:
        return False

    text = automation.template or _DEFAULT_TEMPLATES.get(key, "")
    if not text:
        return False

    wants_push = automation.channel in (MessageChannel.PUSH, MessageChannel.BOTH)
    wants_whatsapp = automation.channel in (MessageChannel.WHATSAPP, MessageChannel.BOTH)
    fired = False

    if wants_push:
        # Free wallet notification (Apple changeMessage + Google addMessage).
        from wallets import service as wallet

        wallet.push_message(customer, text)
        fired = True

    if wants_whatsapp and entitlements.check(merchant, "whatsapp"):
        from messaging import metering

        if _within_quota(merchant, metering):
            from messaging.tasks import send_whatsapp

            send_whatsapp.delay(str(customer.id), text)
            fired = True
        else:
            logger.info("Automation %s WhatsApp skipped for %s: quota exhausted", key, merchant.id)

    return fired


def _within_quota(merchant: Merchant, metering) -> bool:  # type: ignore[no-untyped-def]
    quota = metering.quota_for(merchant)
    return quota is None or metering.used_this_period(merchant) < quota


def run_daily_scan(today: date) -> int:
    """Fire the date-driven automations for every enabled merchant. Returns count."""
    fired = 0
    enabled = Automation.objects.filter(
        enabled=True,
        key__in=[AutomationKey.BIRTHDAY, AutomationKey.EXPIRY, AutomationKey.WINBACK],
    ).select_related("merchant")

    for automation in enabled:
        merchant = automation.merchant
        for customer in _targets(merchant, automation.key, today):
            if dispatch(merchant, customer, automation.key):
                fired += 1
    return fired


def _targets(merchant: Merchant, key: str, today: date):  # type: ignore[no-untyped-def]
    qs = CustomerCard.objects.for_merchant(merchant)
    if key == AutomationKey.BIRTHDAY:
        return qs.filter(birthday__month=today.month, birthday__day=today.day)
    if key == AutomationKey.WINBACK:
        cutoff = today - timedelta(days=LAPSED_DAYS)
        return qs.filter(last_event_at__isnull=False, last_event_at__date=cutoff)
    if key == AutomationKey.EXPIRY:
        # No explicit expiry field in core; approximate as "lapsing soon" —
        # last activity exactly LAPSED_DAYS-7 days ago (a one-week heads-up).
        cutoff = today - timedelta(days=LAPSED_DAYS - 7)
        return qs.filter(last_event_at__isnull=False, last_event_at__date=cutoff)
    return qs.none()
