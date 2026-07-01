# Seed the Plan catalogue from billing.plans.PLAN_LIMITS / PLAN_PRICES_EGP
# (Phase 3). Reversible as a no-op — the hardcoded map remains the fallback.

from __future__ import annotations

from django.db import migrations

PLAN_NAMES = {
    "FREE": "Free",
    "STARTER": "Starter",
    "GROWTH": "Growth",
    "CHAIN": "Chain / Custom",
}


def seed_plans(apps, schema_editor):
    from billing.plans import PLAN_LIMITS, PLAN_PRICES_EGP

    Plan = apps.get_model("billing", "Plan")
    for key, limits in PLAN_LIMITS.items():
        Plan.objects.update_or_create(
            key=str(key),
            defaults={
                "name": PLAN_NAMES[key],
                "price_egp": PLAN_PRICES_EGP[key],
                "is_public": key != "FREE",  # FREE isn't offered at self-serve subscribe
                "archived": False,
                "max_cards": limits["max_cards"],
                "max_locations": limits["max_locations"],
                "max_staff": limits["max_staff"],
                "max_customers": limits["max_customers"],
                "whatsapp": limits["whatsapp"],
                "export": limits["export"],
                "api": limits["api"],
                "specialized_roles": limits["specialized_roles"],
                "custom_branding": limits["custom_branding"],
                "automations": limits["automations"],
                "analytics": limits["analytics"],
                "whatsapp_quota": limits["whatsapp_quota"],
            },
        )


def unseed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Plan.objects.filter(key__in=PLAN_NAMES.keys()).delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0004_plan")]

    operations = [migrations.RunPython(seed_plans, unseed_plans)]
