"""Re-seed the configurable CRM dropdowns.

The 0014 migration seeds them once at install. This command exists for the case
that migration cannot cover: a later release adds a value to an enum in
``console.crm``, and every environment already migrated needs the matching
``CrmChoice`` row without a new data migration.

Safe to run any time — ``ensure_seeded`` only fills gaps and never overwrites an
admin's label, colour or ordering.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from console.crm_seed import ensure_seeded


class Command(BaseCommand):
    help = "Create any missing CRM dropdown rows for the values defined in console.crm."

    def handle(self, *args, **options):
        created = ensure_seeded()
        if created:
            self.stdout.write(self.style.SUCCESS(f"Seeded {created} CRM choice(s)."))
        else:
            self.stdout.write("CRM choices already up to date.")
