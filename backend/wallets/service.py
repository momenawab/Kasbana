"""wallets/service.py — the façade both phases import (contract §3.5).

Phase 1.0 ships working stubs so Joe is never blocked: ``provision`` returns
empty URLs and ``push_update`` is a no-op (it will enqueue
``wallets.tasks.push_pass_update`` once Phase 1.1 lands). Joe's loyalty code does
not change when these become real — that's the point of freezing the seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wallets.interfaces import ProvisionResult

if TYPE_CHECKING:
    from core.models import CustomerCard


def provision(customer_card: CustomerCard) -> ProvisionResult:
    """Provision Apple + Google passes for a card.

    STUB (Phase 1.0): returns empty URLs. Phase 1.1 dispatches to the Apple and
    Google backends and returns real ``apple_pass_url`` / ``google_save_url``.
    """
    return ProvisionResult(apple_pass_url=None, google_save_url=None)


def push_update(customer_card: CustomerCard) -> None:
    """Push a live update to a card's wallet passes.

    STUB (Phase 1.0): no-op. Phase 1.1 enqueues ``wallets.tasks.push_pass_update``
    which sends the Google PATCH and the Apple APNs empty push.
    """
    return None
