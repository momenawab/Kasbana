# Re-sync price + the `api` flag on existing Plan rows from the hardcoded
# catalogue: the new ladder (Starter 599 / Growth 999 / Chain 2,499) and the
# removal of API from the self-serve tiers (api -> False on Growth & Chain;
# API is now bespoke Custom-only). Fresh installs get these via the 0005 seed.
#
# NOTE: dropping `api` on Growth is a downgrade for any existing Growth merchant
# actually using the API — confirm none rely on it before deploying, or add a
# per-merchant grandfather override first.

from __future__ import annotations

from django.db import migrations


def reprice_and_drop_api(apps, schema_editor):
    from billing.plans import PLAN_LIMITS, PLAN_PRICES_EGP

    Plan = apps.get_model("billing", "Plan")
    for key, limits in PLAN_LIMITS.items():
        Plan.objects.filter(key=str(key)).update(
            price_egp=PLAN_PRICES_EGP[key],
            api=limits["api"],
        )


def noop(apps, schema_editor):
    # Irreversible in practice — prior prices/flags aren't recorded here.
    pass


class Migration(migrations.Migration):
    dependencies = [("billing", "0015_sync_automations_allowance")]

    operations = [migrations.RunPython(reprice_and_drop_api, noop)]
