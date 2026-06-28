"""Apple Wallet backend — provisioning + live updates (contract §3.5)."""

from __future__ import annotations

from django.conf import settings

from core.enums import WalletPlatform
from core.models import CustomerCard, WalletRegistration
from wallets.apple import apns
from wallets.apple.config import is_configured


def pass_download_url(customer_card: CustomerCard) -> str:
    """Public link the enrollment page uses to add the pass to Apple Wallet."""
    base = str(settings.BASE_URL or "").rstrip("/")
    return f"{base}/api/v1/wallet/apple/download/{customer_card.id}"


class AppleWalletBackend:
    """Implements WalletProvisioner + WalletUpdater for Apple."""

    def provision(self, customer_card: CustomerCard) -> str | None:
        """Return the .pkpass download URL, or None if signing isn't configured."""
        if not is_configured():
            return None
        return pass_download_url(customer_card)

    def push_update(self, customer_card: CustomerCard) -> None:
        """Send an empty APNs push to every active Apple registration."""
        tokens = list(
            WalletRegistration.objects.filter(
                customer_card=customer_card,
                platform=WalletPlatform.APPLE,
                is_active=True,
            )
            .exclude(push_token="")
            .values_list("push_token", flat=True)
        )
        apns.push_empty(tokens)
