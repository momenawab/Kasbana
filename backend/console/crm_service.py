"""Lead orchestration — the rules that must hold no matter who calls.

Views handle HTTP; this module handles what a lead *means*. It exists because
three invariants have to survive every entry point (public form, console, later
the CSV import), and a rule re-implemented per caller is a rule that drifts:

* every meaningful change lands on the timeline, automatically;
* ``last_activity`` and ``lead_score`` follow the timeline rather than being
  set by hand; and
* a website lead is born with exactly the fields the spec fixes for it.

The timeline is the reason ``log_activity`` is the only way to write an
activity: it also updates the lead's denormalised ``last_activity`` and
re-scores, and those three writes are one logical act.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from console import crm
from console.models import AdminUser, Lead, LeadActivity


def _actor_label(actor: AdminUser | None) -> str:
    """How the timeline names whoever did this. Snapshotted at write time."""
    if actor is None:
        return "System"
    return actor.name or actor.email


def log_activity(
    lead: Lead,
    kind: str,
    title: str,
    *,
    description: str = "",
    actor: AdminUser | None = None,
    rescore: bool = True,
) -> LeadActivity:
    """Append one entry to ``lead``'s timeline and refresh its derived state.

    The single writer for activities. ``rescore`` exists only for callers that
    write several activities in one act (conversion) and would otherwise score
    the same lead repeatedly — the last call leaves it correct either way, since
    scoring is computed from scratch rather than incremented.
    """
    activity = LeadActivity.objects.create(
        lead=lead,
        kind=kind,
        title=title,
        description=description,
        actor=actor,
        actor_label=_actor_label(actor),
    )
    lead.last_activity = title
    lead.save(update_fields=["last_activity", "updated_at"])
    if rescore:
        lead.recalculate_score()
    return activity


@transaction.atomic
def create_website_lead(**fields: Any) -> Lead:
    """Create a lead from the public marketing form.

    Every CRM field is fixed here rather than defaulted on the model: the model
    defaults describe a *manual* lead (the common case in the console), and a
    website lead's shape is a spec'd contract — type, source, unassigned, warm,
    medium, starting score — that should read in one place.
    """
    lead = Lead.objects.create(
        **fields,
        lead_type=crm.LeadType.WEBSITE,
        source=crm.LeadSource.WEBSITE,
        created_by_type=crm.LeadCreatedBy.SYSTEM,
        created_by=None,
        assigned_sales=None,
        status=crm.LeadStatus.NEW_LEAD,
        priority=crm.LeadPriority.MEDIUM,
        temperature=crm.LeadTemperature.WARM,
    )
    log_activity(
        lead,
        crm.ActivityKind.WEBSITE_FORM_SUBMITTED,
        "Website Form Submitted",
        description=f"{lead.name} submitted the Get started form.",
        actor=None,
    )
    return lead


@transaction.atomic
def create_manual_lead(*, actor: AdminUser, **fields: Any) -> Lead:
    """Create a lead by hand from the console. ``source`` is the caller's to
    choose (a walk-in and a referral are both manual); type and creator are not.

    An omitted *or blank* source falls back to Manual — the console sends an
    empty string when the picker is untouched, and a lead whose source reads as
    nothing is worse than one that reads as what it plainly is.
    """
    if not fields.get("source"):
        fields["source"] = crm.LeadSource.MANUAL
    lead = Lead.objects.create(
        **fields,
        lead_type=crm.LeadType.MANUAL,
        created_by_type=crm.LeadCreatedBy.SALES_USER,
        created_by=actor,
    )
    log_activity(
        lead,
        crm.ActivityKind.MANUAL_LEAD_CREATED,
        "Manual Lead Created",
        description=f"Added by {_actor_label(actor)}.",
        actor=actor,
    )
    return lead


# Which field change writes which timeline entry. Only the changes a sales user
# would want to see in the story of the lead — editing a typo'd address is not
# one of them, and a timeline that logs everything gets read for nothing.
_TRACKED_FIELDS: dict[str, tuple[str, str]] = {
    "status": (crm.ActivityKind.STATUS_CHANGED, "Status Changed"),
    "priority": (crm.ActivityKind.PRIORITY_CHANGED, "Priority Changed"),
    "assigned_sales": (crm.ActivityKind.ASSIGNED_SALES_CHANGED, "Assigned Sales Changed"),
}

# Statuses that are milestones in their own right: reaching one writes its own
# entry as well as the status-change entry, because scoring reads these from the
# timeline and a lead that passes through "Proposal Sent" must keep the credit
# even after it moves on to "Negotiation".
_MILESTONE_STATUSES: dict[str, tuple[str, str]] = {
    crm.LeadStatus.DEMO_SCHEDULED: (crm.ActivityKind.DEMO_SCHEDULED, "Demo Scheduled"),
    crm.LeadStatus.DEMO_COMPLETED: (crm.ActivityKind.DEMO_COMPLETED, "Demo Completed"),
    crm.LeadStatus.PROPOSAL_SENT: (crm.ActivityKind.PROPOSAL_SENT, "Proposal Sent"),
    crm.LeadStatus.CLOSED: (crm.ActivityKind.CLOSED, "Closed"),
}


def _display(lead: Lead, field: str) -> str:
    """How a tracked field's value reads on the timeline: the choice's human
    label where there is one, the admin's name for an FK, an em dash for empty.

    Labels come from the model's own choices rather than ``CrmChoice`` — the
    timeline is history, and it should say what the status was called when the
    change happened, not re-render itself if an admin relabels it next year.
    """
    value = getattr(lead, field)
    if isinstance(value, AdminUser):
        return _actor_label(value)
    if value in (None, ""):
        return "—"
    return str(_choices_for(field).get(value, value))


def _choices_for(field: str) -> dict[str, str]:
    choices = getattr(Lead._meta.get_field(field), "choices", None) or []
    return {str(value): str(label) for value, label in choices}


@transaction.atomic
def apply_update(lead: Lead, changes: dict[str, Any], *, actor: AdminUser | None) -> Lead:
    """Apply ``changes`` to ``lead``, logging the ones that tell its story.

    Reads the old values *before* writing so the timeline can say what changed
    from what — the thing a sales user actually wants when they open a lead they
    have not touched in three weeks.
    """
    before = {field: getattr(lead, field) for field in _TRACKED_FIELDS}

    for field, value in changes.items():
        setattr(lead, field, value)

    # Contacting a lead is what "contacted_at" has always meant; keep the old
    # column truthful now that a dedicated "contacted" status no longer exists.
    if "status" in changes and lead.status != crm.LeadStatus.NEW_LEAD and lead.contacted_at is None:
        lead.contacted_at = timezone.now()

    lead.save()

    for field, (kind, title) in _TRACKED_FIELDS.items():
        if field not in changes or before[field] == getattr(lead, field):
            continue
        old_lead = Lead(**{field: before[field]})
        log_activity(
            lead,
            kind,
            title,
            description=f"{_display(old_lead, field)} → {_display(lead, field)}",
            actor=actor,
            rescore=False,
        )

    new_status = changes.get("status")
    if new_status in _MILESTONE_STATUSES and before["status"] != new_status:
        kind, title = _MILESTONE_STATUSES[new_status]
        log_activity(lead, kind, title, actor=actor, rescore=False)

    lead.recalculate_score()
    return lead


def find_duplicates(*, phone: str = "", email: str = "", business_name: str = "", exclude_id=None):
    """Leads that may already be this one.

    Phone and email match exactly; business name matches case-insensitively and
    whole, not as a substring — "Bloom" must not collide with every café in
    Cairo whose name contains it. Deliberately advisory: the caller decides
    whether a hit blocks, merges, or is ignored, because a shop with two
    branches legitimately has two leads on one phone number.
    """
    probes = Q()
    if phone:
        probes |= Q(phone=phone)
    if email:
        probes |= Q(email__iexact=email)
    if business_name:
        probes |= Q(business_name__iexact=business_name.strip())
    if not probes:
        return Lead.objects.none()

    matches = Lead.objects.filter(probes)
    if exclude_id:
        matches = matches.exclude(pk=exclude_id)
    return matches.select_related("assigned_sales")


class MergeError(Exception):
    """A merge that cannot proceed, explained for a salesperson."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# Fields whose values are worth carrying over from the absorbed lead. CRM state
# (status, priority, score, assignment) is deliberately absent: the survivor is
# the record being kept, and its pipeline position is the true one — pulling the
# absorbed lead's status over could drag a "Customer" back to "New Lead". Only
# business facts fill gaps.
_MERGE_FILL_FIELDS: tuple[str, ...] = (
    "name",
    "whatsapp",
    "email",
    "instagram",
    "facebook",
    "website",
    "google_maps_url",
    "logo_url",
    "area",
    "category",
    "address",
    "expected_plan",
    "expected_revenue",
)


@transaction.atomic
def merge_leads(*, survivor: Lead, absorbed: Lead, actor: AdminUser) -> Lead:
    """Fold ``absorbed`` into ``survivor`` and delete it. Returns the survivor.

    The survivor wins every conflict: a field it already has is never
    overwritten, and its pipeline position stands. The absorbed lead only fills
    the survivor's blanks and hands over its history — its calls and its
    timeline move across, so nothing that happened is lost when the row goes.

    Refused when the absorbed lead has been converted: it is linked to a live
    merchant, and deleting it would strand that merchant's origin. Merge the
    other direction, or don't.
    """
    if survivor.pk == absorbed.pk:
        raise MergeError("SAME_LEAD", "A lead cannot be merged into itself.")
    if absorbed.is_converted:
        raise MergeError(
            "ABSORBED_CONVERTED",
            f"{absorbed.business_name} is already a merchant — merge the other lead into it "
            "instead, so the merchant link is kept.",
        )

    # Reparent history before touching the survivor's fields, so a failure here
    # rolls the whole thing back rather than leaving orphaned calls.
    absorbed.calls.update(lead=survivor)
    absorbed.activities.update(lead=survivor)

    filled = []
    for field in _MERGE_FILL_FIELDS:
        if not getattr(survivor, field) and getattr(absorbed, field):
            setattr(survivor, field, getattr(absorbed, field))
            filled.append(field)

    # Merge free-text notes rather than letting one win — a note is the one field
    # where both leads' content is worth keeping verbatim.
    if absorbed.notes and absorbed.notes not in survivor.notes:
        survivor.notes = f"{survivor.notes}\n\n{absorbed.notes}".strip()
        filled.append("notes")

    if filled:
        survivor.save()

    absorbed_label = f"{absorbed.business_name} · {absorbed.phone}"
    absorbed.delete()  # cascades nothing now — its calls and activities moved

    log_activity(
        survivor,
        crm.ActivityKind.DUPLICATE_MERGED,
        "Duplicate Merged",
        description=f"Merged in {absorbed_label}.",
        actor=actor,
    )
    return survivor
