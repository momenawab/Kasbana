"""wallets/interfaces.py — provisioning + live update seams (contract §3.5).

You (Phase 1.1) implement the Apple + Google backends behind these; Joe (Phase 2)
calls only the ``wallets.service`` façade — never ``wallets/apple`` or
``wallets/google`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.models import CustomerCard


@dataclass
class ProvisionResult:
    apple_pass_url: str | None
    google_save_url: str | None


class WalletProvisioner(Protocol):
    def provision(self, customer_card: CustomerCard) -> ProvisionResult: ...


class WalletUpdater(Protocol):
    def push_update(self, customer_card: CustomerCard) -> None: ...
