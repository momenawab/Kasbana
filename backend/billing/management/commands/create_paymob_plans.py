"""Create the Paymob Subscription Plans our tiers map onto (plan §7 / phase 2).

    python manage.py create_paymob_plans --dry-run   # show what would be created
    python manage.py create_paymob_plans             # create the missing ones + save ids
    python manage.py create_paymob_plans --force     # recreate even if already mapped

One Paymob plan per sellable tier per interval (monthly=30d, annual=360d), each
carrying the Moto integration and our subscription webhook URL. Run once per
environment — the ids are per-account, so sandbox and live get different ones.

Already-mapped tiers are skipped, because there is no "get or create" on
Paymob's side: a second run without that guard silently creates a duplicate set
of live plans and orphans the ids we had. ``--force`` opts into that.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from billing.gateways import get_gateway
from billing.models import Plan
from billing.plans import INTERVAL_DAYS, BillingInterval, invalidate_plan_cache, plan_price

# Registered as every plan's ``webhook_url``, so subscription-level events
# (renewals, failures, suspensions) land on the subscription webhook rather than
# the transaction one — a different payload shape and HMAC formula.
SUBSCRIPTION_WEBHOOK_PATH = "/api/v1/billing/webhook/paymob/subscription"


class Command(BaseCommand):
    help = "Create the Paymob Subscription Plans for each sellable tier + interval."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without calling Paymob or writing.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate plans for tiers that already carry a Paymob plan id.",
        )
        parser.add_argument(
            "--webhook-url",
            default="",
            help=f"Override the webhook URL (default: BASE_URL{SUBSCRIPTION_WEBHOOK_PATH}).",
        )
        parser.add_argument(
            "--retrial-days",
            default="",
            help="Days Paymob retries a failed deduction before giving up.",
        )
        parser.add_argument(
            "--reminder-days",
            default="",
            help="Days before a deduction that Paymob emails the customer.",
        )

    def handle(self, *args, **opts):
        gateway = get_gateway("paymob")
        webhook_url = opts["webhook_url"] or f"{settings.BASE_URL}{SUBSCRIPTION_WEBHOOK_PATH}"

        if not webhook_url.startswith("https://") and not opts["dry_run"]:
            # Paymob calls this from the outside world; a localhost/http URL
            # silently yields a plan whose renewals we never hear about.
            raise CommandError(
                f"Refusing to register a non-HTTPS webhook URL: {webhook_url}\n"
                "Set BASE_URL to the public host, or pass --webhook-url."
            )

        # ``is_public`` is exactly "offered on the self-serve subscribe screen",
        # so it's the right source for which tiers need a Paymob plan. FREE is
        # not public; a 0-price tier can't be a subscription anyway.
        sellable = Plan.objects.filter(is_public=True, archived=False)
        tiers = [p for p in sellable if not self._free(p)]
        if not tiers:
            raise CommandError("No sellable plans found — has the seed migration run?")

        self.stdout.write(self.style.MIGRATE_HEADING("Paymob subscription plans"))
        self.stdout.write(f"  webhook_url:  {webhook_url}")
        self.stdout.write(f"  moto id:      {self._moto_id() or self.style.ERROR('(missing)')}")
        self.stdout.write(f"  mode:         {'DRY RUN' if opts['dry_run'] else 'live'}\n")

        created, skipped = 0, 0
        for plan in tiers:
            for interval in BillingInterval.values:
                existing = plan.paymob_plan_id(interval)
                if existing and not opts["force"]:
                    self.stdout.write(f"  · {plan.key:8} {interval:8} already mapped → {existing}")
                    skipped += 1
                    continue

                frequency = INTERVAL_DAYS[interval]
                amount = plan_price(plan.key, interval)
                name = f"Stampn {plan.name} ({interval})"

                if opts["dry_run"]:
                    self.stdout.write(
                        f"  + {plan.key:8} {interval:8} would create: "
                        f"{amount} EGP every {frequency}d — {name!r}"
                    )
                    created += 1
                    continue

                paymob_id = gateway.create_subscription_plan(
                    name=name,
                    amount_egp=amount,
                    frequency=frequency,
                    webhook_url=webhook_url,
                    reminder_days=opts["reminder_days"],
                    retrial_days=opts["retrial_days"],
                )
                field = (
                    "paymob_plan_id_annual"
                    if interval == BillingInterval.ANNUAL
                    else "paymob_plan_id_monthly"
                )
                setattr(plan, field, paymob_id)
                plan.save(update_fields=[field, "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {plan.key:8} {interval:8} {amount} EGP / {frequency}d → {paymob_id}"
                    )
                )
                created += 1

        if not opts["dry_run"]:
            invalidate_plan_cache()

        verb = "would create" if opts["dry_run"] else "created"
        self.stdout.write(f"\n{verb} {created}, skipped {skipped} (already mapped).")
        if opts["dry_run"]:
            self.stdout.write("Re-run without --dry-run to create them.")

    def _free(self, plan: Plan) -> bool:
        return plan.price_egp <= Decimal("0")

    def _moto_id(self) -> str:
        # Display only — the adapter is what refuses to build a plan without it.
        return str(settings.BILLING.get("PAYMOB", {}).get("MOTO_INTEGRATION_ID", "") or "")
