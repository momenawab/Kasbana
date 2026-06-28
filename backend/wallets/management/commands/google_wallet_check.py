"""Live verification for Google Wallet credentials (Phase 1.1 go-live).

    python manage.py google_wallet_check            # config + API auth (read-only)
    python manage.py google_wallet_check --sync-demo  # also create a demo class +
                                                      # print a real save URL

Run on the server (where the SA key + issuer id are configured). The read-only
check proves the service account can authenticate and reach the Wallet API; the
demo sync proves class creation + save-URL generation end to end.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from wallets.google import config


class Command(BaseCommand):
    help = "Verify Google Wallet credentials and API access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-demo",
            action="store_true",
            help="Create a throwaway demo class + customer card and print a save URL.",
        )

    def handle(self, *args, **opts):
        issuer = config.issuer_id()
        sa = config.load_service_account()

        self.stdout.write(self.style.MIGRATE_HEADING("Google Wallet configuration"))
        self.stdout.write(f"  issuer_id:      {issuer or '(missing)'}")
        self.stdout.write(f"  service acct:   {sa.client_email if sa else '(missing key)'}")
        self.stdout.write(f"  configured:     {config.is_configured()}")

        if not config.is_configured():
            self.stdout.write(
                self.style.WARNING(
                    "\nNot fully configured. Set GOOGLE_WALLET_ISSUER_ID and "
                    "GOOGLE_SA_KEY_PATH, then re-run."
                )
            )
            return

        # Read-only API auth check.
        from wallets.google.client import _access_token

        token = _access_token()
        if token:
            self.stdout.write(self.style.SUCCESS("\n✓ Authenticated to the Wallet API."))
        else:
            self.stdout.write(self.style.ERROR("\n✗ Could not obtain an access token."))
            return

        if not opts["sync_demo"]:
            self.stdout.write("\nRun with --sync-demo to create a class + save URL.")
            return

        self._sync_demo()

    def _sync_demo(self):
        from django.db import transaction

        from core.enums import CardStatus, CardType
        from core.models import Card, CustomerCard, Merchant
        from wallets.google.client import build_save_url, sync_class

        with transaction.atomic():
            merchant, _ = Merchant.objects.get_or_create(
                slug="kasbana-demo", defaults={"name": "Kasbana Demo"}
            )
            card, _ = Card.objects.get_or_create(
                merchant=merchant,
                name="Demo Stamp Card",
                defaults={
                    "type": CardType.STAMP,
                    "stamps_required": 5,
                    "reward_title": "Free coffee",
                    "status": CardStatus.ACTIVE,
                },
            )
            cid = sync_class(card)
            self.stdout.write(self.style.SUCCESS(f"✓ Class synced: {cid}"))

            cc, _ = CustomerCard.objects.get_or_create(
                card=card, customer_phone="+201000000000", merchant=merchant
            )
            url = build_save_url(cc)
            self.stdout.write(self.style.SUCCESS("✓ Save URL (open on an Android phone):"))
            self.stdout.write(f"\n{url}\n")
