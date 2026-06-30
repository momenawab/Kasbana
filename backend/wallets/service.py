"""wallets/service.py — the façade both phases import (contract §3.5).

Dispatches to the Apple + Google backends. ``loyalty/`` (Joe) calls only this
module — never ``wallets/apple`` or ``wallets/google`` directly. Each platform
degrades to a no-op / null URL when its credentials are absent, so enrollment
and stamping keep working in environments without wallet secrets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wallets.apple.client import AppleWalletBackend
from wallets.google.client import GoogleWalletBackend
from wallets.interfaces import ProvisionResult

if TYPE_CHECKING:
    from core.models import CustomerCard

_apple = AppleWalletBackend()
_google = GoogleWalletBackend()


def provision(customer_card: CustomerCard) -> ProvisionResult:
    """Provision Apple + Google passes; returns the add-to-wallet URLs."""
    return ProvisionResult(
        apple_pass_url=_apple.provision(customer_card),
        google_save_url=_google.provision(customer_card),
    )


def push_update(customer_card: CustomerCard) -> None:
    """Push a live update to a card's wallet passes (both platforms).

    Enqueues ``wallets.tasks.push_pass_update`` so the HTTP request returns fast;
    the Celery worker does the Google PATCH + Apple APNs push.
    """
    from wallets.tasks import push_pass_update

    push_pass_update.delay(str(customer_card.id))


def push_message(customer_card: CustomerCard, body: str, *, title: str = "") -> None:
    """Send a free text notification to a card's wallet passes (both platforms).

    Persists the message synchronously (so the Apple pass renders it the moment a
    device re-pulls) and enqueues ``wallets.tasks.push_wallet_message`` for the
    network calls (Google ``addMessage`` + Apple APNs ping). Unlike WhatsApp this
    costs nothing — it rides APNs / the Google Wallet API.
    """
    from wallets.models import WalletMessage
    from wallets.tasks import push_wallet_message

    WalletMessage.objects.create(customer_card=customer_card, title=title, body=body)
    push_wallet_message.delay(str(customer_card.id), title, body)
