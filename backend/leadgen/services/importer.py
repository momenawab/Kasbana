"""Handing a generated lead over to the CRM.

The single crossing point between prospecting and sales. Everything upstream of
here is ours; everything downstream belongs to ``console`` and must not be able
to tell that a lead arrived from a search job rather than a phone call.

Which is why import goes through ``crm_service.create_manual_lead`` rather than
``Lead.objects.create``: that function owns invariants the CRM depends on — the
timeline entry, ``last_activity``, the initial score — and a lead created around
it would be subtly different from every other lead in the pipeline forever.

The fit score is deliberately **not** written to ``Lead.lead_score``. That field
measures engagement and is recomputed from the CRM timeline on every activity
(``crm_service.log_activity``), so anything we wrote there would be both wrong
and short-lived. It travels in the opening note instead, where it stays true as
a statement about what discovery found.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from console import crm, crm_service
from console.models import AdminUser
from console.models import Lead as CrmLead
from leadgen import enums
from leadgen.models import GeneratedLead

logger = logging.getLogger(__name__)


class ImportError_(RuntimeError):
    """The lead cannot be imported. Message is operator-facing."""


def import_lead(
    lead: GeneratedLead,
    *,
    actor: AdminUser,
    assigned_sales: AdminUser | None = None,
    force: bool = False,
) -> CrmLead:
    """Create a CRM lead from ``lead``. Returns the new CRM record.

    A CRM match blocks the import unless ``force`` is set. The block is
    deliberate but overridable: a shared landline across a food court, or a
    chain's head-office number on every branch, both produce legitimate matches
    that a rep should be able to import anyway — with their eyes open.
    """
    if lead.imported_lead_id:
        raise ImportError_(f"{lead.business_name} was already imported.")
    if lead.duplicate_of_id:
        raise ImportError_(
            f"{lead.business_name} is a duplicate of another discovered lead — "
            "import the one it was merged into."
        )
    if lead.crm_match_id and not force:
        raise ImportError_(
            f"{lead.business_name} already looks like an existing CRM lead "
            f"(matched on {lead.crm_match_reason}). Confirm to import anyway."
        )

    with transaction.atomic():
        crm_lead = crm_service.create_manual_lead(
            actor=actor,
            **_crm_fields(lead, assigned_sales),
        )
        crm_service.log_activity(
            crm_lead,
            crm.ActivityKind.NOTE_ADDED,
            "Imported from Lead Generation",
            description=_opening_note(lead),
            actor=actor,
        )

        lead.imported_lead = crm_lead
        lead.imported_at = timezone.now()
        lead.state = enums.LeadState.IMPORTED
        lead.save(update_fields=["imported_lead", "imported_at", "state", "updated_at"])

        job = lead.job
        job.imported_count = job.leads.filter(imported_lead__isnull=False).count()
        job.save(update_fields=["imported_count", "updated_at"])

    logger.info(
        "leadgen.import.created",
        extra={"generated_lead": str(lead.id), "crm_lead": str(crm_lead.id)},
    )
    return crm_lead


def _crm_fields(lead: GeneratedLead, assigned_sales: AdminUser | None) -> dict:
    """Map a discovered business onto the CRM's lead fields.

    ``name`` is the person a rep asks for. An empty owner name is the common
    outcome here — most small Egyptian businesses publish nothing — and it is
    left empty on purpose rather than filled with the business name, which would
    put a rep on the phone greeting a shop as though it were a person. The
    opening note tells them to ask instead.
    """
    profile = getattr(lead, "website_profile", None)
    socials = {s.platform: s.url for s in lead.socials.all()}

    return {
        "business_name": lead.business_name[:160],
        "name": lead.owner_name[:120],
        "phone": lead.phone_e164 or lead.phone,
        "email": (profile.emails[0] if profile and profile.emails else "")[:254],
        "website": lead.website if lead.website_domain else "",
        "instagram": socials.get(enums.SocialPlatform.INSTAGRAM, "")[:120],
        "facebook": socials.get(enums.SocialPlatform.FACEBOOK, "")[:200],
        "whatsapp": socials.get(enums.SocialPlatform.WHATSAPP, "")[:40],
        "google_maps_url": lead.google_maps_url,
        "logo_url": (profile.logo_url if profile else "")[:500],
        "address": lead.address[:255],
        "area": _area_from(lead),
        "category": lead.category,
        "source": crm.LeadSource.GOOGLE_MAPS,
        "assigned_sales": assigned_sales,
        # No published owner means the first job is to find out who it is, so
        # the lead lands with a call queued rather than sitting actionless.
        "next_action": "" if lead.owner_name else crm.NextAction.CALL_TOMORROW,
    }


def _area_from(lead: GeneratedLead) -> str:
    """The neighbourhood, taken from the address rather than the job's city.

    A job scoped to "Cairo / Maadi" produces leads across several districts once
    discovery splits into sub-cells, so stamping every one with the job's street
    would be wrong for most of them.
    """
    parts = [part.strip() for part in lead.address.split(",") if part.strip()]
    # Egyptian formatted addresses run narrow → wide; the second component is
    # usually the district ("12 Road 9, Maadi, Cairo Governorate").
    return (parts[1] if len(parts) > 1 else (parts[0] if parts else ""))[:120]


def _opening_note(lead: GeneratedLead) -> str:
    """What a rep should know before dialling, in the order they need it.

    The fit score lives here rather than in ``lead_score`` because that column
    means engagement and is recomputed from the timeline; a number written there
    would be overwritten by the first activity anyway.
    """
    lines = [
        f"Discovered by Lead Generation — fit score {lead.fit_score}/100 "
        f"({lead.get_score_label_display() if lead.score_label else 'unscored'}).",
        f"{lead.reviews_count} Google reviews"
        + (f", rated {lead.rating}" if lead.rating else "")
        + (f", {lead.branch_count} branches found" if lead.branch_count > 1 else "")
        + ".",
    ]

    if lead.owner_name:
        source = lead.get_owner_name_source_display()
        lines.append(
            f"Owner appears to be {lead.owner_name} "
            f"(from {source.lower()}, {lead.owner_name_confidence} confidence) — worth confirming."
        )
    else:
        lines.append(
            "No owner name published — ask who owns the place on the first call."
        )

    profile = getattr(lead, "website_profile", None)
    if profile and profile.pos_vendors:
        lines.append(f"Runs {', '.join(profile.pos_vendors)} on the POS side.")
    if profile and profile.loyalty_vendors:
        lines.append(
            f"Already uses {', '.join(profile.loyalty_vendors)} for loyalty — "
            "this is a displacement sale."
        )
    if profile and profile.delivery_platforms:
        lines.append(f"On {', '.join(profile.delivery_platforms)}.")

    if lead.score_breakdown:
        fired = [row["label"] for row in lead.score_breakdown if row["points"] > 0]
        if fired:
            lines.append("Signals: " + ", ".join(fired) + ".")

    return "\n".join(lines)


def import_many(
    leads, *, actor: AdminUser, assigned_sales: AdminUser | None = None, force: bool = False
) -> tuple[list[CrmLead], list[tuple[GeneratedLead, str]]]:
    """Import several leads, reporting per-lead failures rather than aborting.

    A bulk import of fifty leads where one is a duplicate should import the
    other forty-nine and say what happened to the one — not roll back the lot
    and make the operator find the offender by hand.
    """
    created: list[CrmLead] = []
    failed: list[tuple[GeneratedLead, str]] = []

    for lead in leads:
        try:
            created.append(
                import_lead(lead, actor=actor, assigned_sales=assigned_sales, force=force)
            )
        except ImportError_ as exc:
            failed.append((lead, str(exc)))

    return created, failed
