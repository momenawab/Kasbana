"""Move the leads that already exist onto the CRM vocabulary.

0013 widened the schema; this fills it in. Every pre-CRM lead came from the
marketing form — that was the only thing that could create one — so they all
backfill as website leads created by the system.

The status remap matters most: the old field held ``new`` / ``contacted``, and
0013 left those strings sitting in rows that the new choices no longer name.
Django does not enforce choices at the database level, so nothing has broken
loudly — the values are simply unreadable to the new code, which is exactly the
kind of quiet wrongness worth fixing in the same release that causes it.

``contacted`` maps to ``contact_attempted`` rather than one of the richer
"answered" statuses: the old model recorded only that someone reached out, not
how it went, and inventing a warmer status than the data supports would put
leads in front of sales as more qualified than they are.
"""

from __future__ import annotations

from django.db import migrations

from console.crm_seed import ensure_seeded

# old value → new value. Anything else (there should be nothing) is left alone
# and lands on the model default at next save.
_STATUS_REMAP = {
    "new": "new_lead",
    "contacted": "contact_attempted",
}

# A website lead's starting score. Not a magic number: it is what
# ``crm.score_lead`` computes for medium priority + warm + a website submission
# with no calls yet (8 + 12 + 5). Hard-coded here because a migration must not
# import live scoring logic that may be re-tuned in a later release.
_WEBSITE_START_SCORE = 25


def backfill(apps, schema_editor):
    Lead = apps.get_model("console", "Lead")
    LeadActivity = apps.get_model("console", "LeadActivity")
    CrmChoice = apps.get_model("console", "CrmChoice")

    ensure_seeded(CrmChoice)

    for old, new in _STATUS_REMAP.items():
        Lead.objects.filter(status=old).update(status=new)

    Lead.objects.update(
        lead_type="website",
        source="website",
        created_by_type="system",
        priority="medium",
        temperature="warm",
        lead_score=_WEBSITE_START_SCORE,
        last_activity="Website Form Submitted",
    )

    # Give each existing lead the timeline entry it would have had if the CRM
    # had existed when it arrived, so the details page is never blank. Dated to
    # the lead's own created_at, not now — the submission happened when it
    # happened. (auto_now_add ignores an assigned value on insert, hence the
    # second pass to set it.)
    existing = set(LeadActivity.objects.values_list("lead_id", flat=True))
    for lead in Lead.objects.exclude(id__in=existing).iterator():
        activity = LeadActivity.objects.create(
            lead_id=lead.id,
            kind="website_form_submitted",
            title="Website Form Submitted",
            description=f"{lead.name} submitted the Get started form.",
            actor_label="System",
        )
        LeadActivity.objects.filter(pk=activity.pk).update(created_at=lead.created_at)


def unbackfill(apps, schema_editor):
    """Put the two old status values back so 0013 can reverse cleanly."""
    Lead = apps.get_model("console", "Lead")
    for old, new in _STATUS_REMAP.items():
        Lead.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):
    dependencies = [("console", "0013_crm_lead_expansion")]

    operations = [migrations.RunPython(backfill, unbackfill)]
