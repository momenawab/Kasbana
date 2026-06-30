"""Messaging Celery tasks (Phase 1.7) — WhatsApp send + automation scan.

``send_whatsapp`` is the single dispatch path: it sends via ``WhatsAppClient``
and meters the send against the merchant's monthly quota. Quota *gating* (402)
happens at the API edge before enqueue; metering here records what was actually
dispatched. Routed to the ``messaging`` queue (settings ``CELERY_TASK_ROUTES``).
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from core.models import CustomerCard, Merchant

logger = logging.getLogger(__name__)


@shared_task(queue="messaging")
def send_whatsapp(customer_card_id: str, text: str) -> str:
    """Send one WhatsApp text to a customer and meter it. Returns message id."""
    from messaging import metering
    from messaging.whatsapp import WhatsAppClient

    customer = CustomerCard.objects.select_related("merchant").get(pk=customer_card_id)
    result = WhatsAppClient().send_text(to=customer.customer_phone, text=text)
    if result.ok:
        metering.record_send(customer.merchant, count=1)
    return result.message_id


@shared_task(queue="messaging")
def send_campaign(campaign_id: str) -> int:
    """Fan a campaign out to its segment; returns the number dispatched."""
    from messaging.enums import CampaignStatus, MessageChannel
    from messaging.models import Campaign
    from messaging.segments import resolve

    campaign = Campaign.objects.select_related("merchant").get(pk=campaign_id)
    campaign.status = CampaignStatus.SENDING
    campaign.save(update_fields=["status", "updated_at"])

    recipients = list(resolve(campaign.merchant, campaign.audience))
    wants_push = campaign.channel in (MessageChannel.PUSH, MessageChannel.BOTH)
    wants_whatsapp = campaign.channel in (MessageChannel.WHATSAPP, MessageChannel.BOTH)
    sent = 0
    for customer in recipients:
        if wants_whatsapp:
            send_whatsapp.delay(str(customer.id), campaign.message)
        if wants_push:
            # Free wallet notification (Apple changeMessage + Google addMessage).
            from wallets import service as wallet

            wallet.push_message(customer, campaign.message)
        sent += 1

    campaign.status = CampaignStatus.SENT
    campaign.sent_at = timezone.now()
    campaign.delivered = sent
    campaign.save(update_fields=["status", "sent_at", "delivered", "updated_at"])
    return sent


@shared_task(queue="messaging")
def scan_automations() -> int:
    """Daily beat: fire date-driven automations (birthday / expiry / winback).

    Event-driven automations (reward_ready / welcome) fire inline from the
    ledger hooks; this pass handles the ones that depend on the calendar.
    """
    from messaging.automation import run_daily_scan

    return run_daily_scan(timezone.localdate())


def fire_for_customer(merchant: Merchant, customer: CustomerCard, key: str) -> None:
    """Dispatch an enabled automation for a single customer (ledger hooks)."""
    from messaging.automation import dispatch

    dispatch(merchant, customer, key)
