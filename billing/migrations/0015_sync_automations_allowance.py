# Re-sync the per-plan `automations` allowance on existing rows from the
# hardcoded catalogue after engagement automations became a Growth+ feature
# (Starter dropped 2 -> 0; `welcome` is exempt from the count). Fresh installs
# already get the new values via the 0005 seed, which reads live PLAN_LIMITS.

from __future__ import annotations

from django.db import migrations


def sync_automations(apps, schema_editor):
    from billing.plans import PLAN_LIMITS

    Plan = apps.get_model("billing", "Plan")
    for key, limits in PLAN_LIMITS.items():
        Plan.objects.filter(key=str(key)).update(automations=limits["automations"])


def noop(apps, schema_editor):
    # Irreversible in practice — the previous allowances aren't recorded here.
    pass


class Migration(migrations.Migration):
    dependencies = [("billing", "0014_plan_referral")]

    operations = [migrations.RunPython(sync_automations, noop)]
