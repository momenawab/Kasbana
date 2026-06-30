"""wallets Celery tasks (contract §3.9). Queue: ``wallet``.

Canonical task names are frozen. Each degrades to a no-op when the relevant
wallet credentials are absent.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="wallets.tasks.provision_pass")
def provision_pass(customer_card_id: str) -> None:
    """Ensure Google class exists + object provisioned for a card.

    The Apple pass is built on demand by the web service; Google needs the class
    to exist before a save URL works, which provision() handles. This task is a
    hook for any heavier async provisioning.
    """
    from core.models import CustomerCard
    from wallets.google.client import GoogleWalletBackend

    cc = CustomerCard.objects.select_related("card", "merchant").filter(id=customer_card_id).first()
    if cc is None:
        logger.warning("provision_pass: CustomerCard %s not found", customer_card_id)
        return
    GoogleWalletBackend().provision(cc)


@shared_task(name="wallets.tasks.push_pass_update")
def push_pass_update(customer_card_id: str) -> None:
    """Push a live update: Google PATCH + Apple APNs empty push."""
    from core.models import CustomerCard
    from wallets.apple.client import AppleWalletBackend
    from wallets.google.client import GoogleWalletBackend

    cc = CustomerCard.objects.select_related("card", "merchant").filter(id=customer_card_id).first()
    if cc is None:
        logger.warning("push_pass_update: CustomerCard %s not found", customer_card_id)
        return
    GoogleWalletBackend().push_update(cc)
    AppleWalletBackend().push_update(cc)


@shared_task(name="wallets.tasks.push_wallet_message")
def push_wallet_message(customer_card_id: str, title: str, body: str) -> None:
    """Deliver a free wallet notification: Google addMessage + Apple APNs ping.

    The ``WalletMessage`` row is already persisted by ``service.push_message``, so
    the Apple pass renders it on the device's next pull (triggered by the ping).
    """
    from core.models import CustomerCard
    from wallets.apple.client import AppleWalletBackend
    from wallets.google.client import GoogleWalletBackend

    cc = CustomerCard.objects.select_related("card", "merchant").filter(id=customer_card_id).first()
    if cc is None:
        logger.warning("push_wallet_message: CustomerCard %s not found", customer_card_id)
        return
    GoogleWalletBackend().add_message(cc, header=title, body=body)
    AppleWalletBackend().push_message(cc)


@shared_task(name="wallets.tasks.sync_google_class")
def sync_google_class(card_id: str) -> None:
    """Create/update the Google LoyaltyClass for a Card (e.g. after edits)."""
    from core.models import Card
    from wallets.google.client import sync_class

    card = Card.objects.select_related("merchant").filter(id=card_id).first()
    if card is None:
        logger.warning("sync_google_class: Card %s not found", card_id)
        return
    sync_class(card)
