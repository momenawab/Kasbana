"""wallets Celery tasks (contract §3.9). Queue: ``wallet``.

Canonical task names are frozen. Phase 1.0 ships no-op bodies; Phase 1.1 fills
them in (Apple .pkpass build / APNs push, Google class+object sync).
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name="wallets.tasks.provision_pass")
def provision_pass(customer_card_id: str) -> None:
    """Build + provision Apple and Google passes for a card. STUB (Phase 1.1)."""
    return None


@shared_task(name="wallets.tasks.push_pass_update")
def push_pass_update(customer_card_id: str) -> None:
    """Push a live update (Google PATCH + Apple APNs empty push). STUB (Phase 1.1)."""
    return None


@shared_task(name="wallets.tasks.sync_google_class")
def sync_google_class(card_id: str) -> None:
    """Create/update the Google LoyaltyClass for a Card. STUB (Phase 1.1)."""
    return None
