"""Seeding for the configurable CRM dropdowns.

``ensure_seeded`` materialises one ``CrmChoice`` row per code-level value in
``crm.SYSTEM_CHOICES``, so Settings → CRM Configuration has something to show on
a fresh install and every system value arrives pre-labelled and pre-coloured.

It is idempotent and *non-destructive*: an existing row is never overwritten,
because an admin may have re-labelled or re-coloured it and their edit outranks
our default. It only ever fills gaps — which is what makes it safe to re-run
from a data migration on every release when a new enum value lands.

The one thing it does force is ``is_system=True``: that flag is the code's
claim, not the admin's, and it is what stops the row being deleted.
"""

from __future__ import annotations

from console import crm

# Badge colours for the values worth distinguishing at a glance. Anything absent
# seeds with an empty colour and renders in the console's neutral badge — that is
# a deliberate default, not an omission: colouring all 24 statuses would make the
# table louder without making it more readable.
_DEFAULT_COLORS: dict[str, dict[str, str]] = {
    crm.CrmChoiceKind.STATUS: {
        crm.LeadStatus.NEW_LEAD: "#3b82f6",  # blue — untouched
        crm.LeadStatus.INTERESTED: "#8b5cf6",
        crm.LeadStatus.VERY_INTERESTED: "#7c3aed",
        crm.LeadStatus.HOT_LEAD: "#ef4444",  # red — move now
        crm.LeadStatus.DEMO_SCHEDULED: "#f59e0b",
        crm.LeadStatus.DEMO_COMPLETED: "#f59e0b",
        crm.LeadStatus.PROPOSAL_SENT: "#f59e0b",
        crm.LeadStatus.NEGOTIATION: "#f59e0b",
        crm.LeadStatus.CUSTOMER: "#10b981",  # green — won
        crm.LeadStatus.CONVERTED: "#059669",
        crm.LeadStatus.NOT_INTERESTED: "#6b7280",  # grey — dead
        crm.LeadStatus.TOO_EXPENSIVE: "#6b7280",
        crm.LeadStatus.USING_COMPETITOR: "#6b7280",
        crm.LeadStatus.DO_NOT_CALL_AGAIN: "#4b5563",
        crm.LeadStatus.CLOSED: "#6b7280",
    },
    crm.CrmChoiceKind.PRIORITY: {
        crm.LeadPriority.HIGH: "#ef4444",
        crm.LeadPriority.MEDIUM: "#f59e0b",
        crm.LeadPriority.LOW: "#6b7280",
    },
    crm.CrmChoiceKind.TEMPERATURE: {
        crm.LeadTemperature.HOT: "#ef4444",
        crm.LeadTemperature.WARM: "#f59e0b",
        crm.LeadTemperature.COLD: "#3b82f6",
    },
}

# Categories ship with the verticals Stampn actually sells to, so the dropdown
# is useful on day one. Unlike every other kind these are NOT system rows —
# there is no enum behind them and no code reads them, so an admin may rename or
# delete any of these freely.
_SEED_CATEGORIES: tuple[str, ...] = (
    "Café",
    "Restaurant",
    "Bakery",
    "Juice Bar",
    "Salon",
    "Barber Shop",
    "Spa",
    "Gym",
    "Pharmacy",
    "Retail Shop",
    "Other",
)


def ensure_seeded(choice_model=None) -> int:
    """Create any missing system rows (and the starter categories). Returns the
    number of rows created.

    ``choice_model`` lets a migration pass its historical ``CrmChoice`` — inside
    a migration the real model may not match the frozen schema, so never import
    it directly there.
    """
    if choice_model is None:  # pragma: no cover — exercised via the management command
        from console.models import CrmChoice as choice_model  # noqa: N813

    created = 0
    for kind, enum in crm.SYSTEM_CHOICES.items():
        colors = _DEFAULT_COLORS.get(kind, {})
        for order, value in enumerate(enum.values):
            _, was_created = choice_model.objects.get_or_create(
                kind=kind,
                slug=value,
                defaults={
                    "label": enum(value).label,
                    "color": colors.get(value, ""),
                    "order": order,
                    "is_system": True,
                    "is_active": True,
                },
            )
            created += int(was_created)

        # A pre-existing row must still be flagged system — the flag is the
        # code's claim on the slug, and it is what refuses the delete.
        choice_model.objects.filter(kind=kind, slug__in=list(enum.values)).exclude(
            is_system=True
        ).update(is_system=True)

    for order, label in enumerate(_SEED_CATEGORIES):
        _, was_created = choice_model.objects.get_or_create(
            kind=crm.CrmChoiceKind.CATEGORY,
            slug=label.lower().replace(" ", "_").replace("é", "e"),
            defaults={"label": label, "order": order, "is_system": False, "is_active": True},
        )
        created += int(was_created)

    return created
