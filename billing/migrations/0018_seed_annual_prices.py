# Seed `price_egp_annual` on existing Plan rows from the hardcoded catalogue
# (Starter 5,990 / Growth 9,990 / Chain 24,990 — ten months' worth of the
# monthly price, the "2 months free" framing the pricing page advertises).
# 0017 adds the column defaulted to 0; without this, every annual checkout would
# price at 0. Fresh installs still run 0005 (monthly-only) then land here.
#
# Deliberately does NOT touch the paymob_plan_id_* columns: those are per
# environment (sandbox vs live) and come from `manage.py create_paymob_plans`.

from __future__ import annotations

from django.db import migrations


def seed_annual_prices(apps, schema_editor):
    from billing.plans import PLAN_PRICES_EGP_ANNUAL

    Plan = apps.get_model("billing", "Plan")
    for key, price in PLAN_PRICES_EGP_ANNUAL.items():
        Plan.objects.filter(key=str(key)).update(price_egp_annual=price)


def noop(apps, schema_editor):
    # Irreversible in practice — there is no prior annual price to restore.
    pass


class Migration(migrations.Migration):
    dependencies = [("billing", "0017_paymob_recurring_subscription")]

    operations = [migrations.RunPython(seed_annual_prices, noop)]
