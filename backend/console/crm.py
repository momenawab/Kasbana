"""The CRM vocabulary + lead scoring — the sales pipeline's shared language.

Every CRM dropdown in the console reads from here. The enums below are the
*system* values: code depends on them (scoring keys off priority/temperature,
conversion keys off ``LeadStatus.CONVERTED``, the KPI cards count INTERESTED /
DEMO_SCHEDULED / CUSTOMER by name), so they cannot be renamed away or deleted.
Admins re-label, re-colour and re-order them — and add their *own* values —
through ``CrmChoice`` rows in ``console.models``, which overlay these. That
split is deliberate: a status an admin invents must never be able to break the
scoring maths or strand a lead mid-conversion.

``CrmChoiceKind`` names the dropdowns an admin may configure. Two of them
(CATEGORY) have no enum here at all — a business category is pure taxonomy with
no logic attached, so those rows are admin-created from empty.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone


class LeadType(models.TextChoices):
    """How the lead entered the system — the *only* difference between the two."""

    WEBSITE = "website", "Website"
    MANUAL = "manual", "Manual"


class LeadCreatedBy(models.TextChoices):
    """Who created it. SYSTEM means the public marketing form, unattended."""

    SYSTEM = "system", "System"
    SALES_USER = "sales_user", "Sales User"


class LeadStatus(models.TextChoices):
    """The pipeline. Ordered roughly as a lead progresses, since the console
    renders them in declaration order until an admin overrides ``order``."""

    NEW_LEAD = "new_lead", "New Lead"
    CONTACT_ATTEMPTED = "contact_attempted", "Contact Attempted"
    NO_ANSWER = "no_answer", "No Answer"
    BUSY = "busy", "Busy"
    PHONE_OFF = "phone_off", "Phone Off"
    WRONG_NUMBER = "wrong_number", "Wrong Number"
    RECEPTION_ANSWERED = "reception_answered", "Reception Answered"
    MANAGER_ANSWERED = "manager_answered", "Manager Answered"
    OWNER_ANSWERED = "owner_answered", "Owner Answered"
    INTERESTED = "interested", "Interested"
    VERY_INTERESTED = "very_interested", "Very Interested"
    HOT_LEAD = "hot_lead", "Hot Lead"
    DEMO_SCHEDULED = "demo_scheduled", "Demo Scheduled"
    DEMO_COMPLETED = "demo_completed", "Demo Completed"
    PROPOSAL_SENT = "proposal_sent", "Proposal Sent"
    NEGOTIATION = "negotiation", "Negotiation"
    WAITING_CUSTOMER = "waiting_customer", "Waiting Customer"
    TOO_EXPENSIVE = "too_expensive", "Too Expensive"
    USING_COMPETITOR = "using_competitor", "Using Competitor"
    NOT_INTERESTED = "not_interested", "Not Interested"
    CUSTOMER = "customer", "Customer"
    CONVERTED = "converted", "Converted"
    DO_NOT_CALL_AGAIN = "do_not_call_again", "Do Not Call Again"
    CLOSED = "closed", "Closed"


# Statuses the *code* reads by name. Re-labelling one is fine; these exist so a
# reader can see at a glance which slugs are load-bearing and why deleting a
# system CrmChoice is refused.
LOGIC_BEARING_STATUSES: frozenset[str] = frozenset(
    {
        LeadStatus.CONVERTED,  # set by Convert-To-Merchant; gates re-conversion
        LeadStatus.CUSTOMER,  # KPI: Customers
        LeadStatus.INTERESTED,  # KPI: Interested
        LeadStatus.DEMO_SCHEDULED,  # KPI: Demo Scheduled + scoring
        LeadStatus.PROPOSAL_SENT,  # scoring
    }
)

# Reaching any of these means the lead is done — no follow-up is chased, and the
# overdue-follow-up KPI skips them.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        LeadStatus.CONVERTED,
        LeadStatus.CUSTOMER,
        LeadStatus.NOT_INTERESTED,
        LeadStatus.DO_NOT_CALL_AGAIN,
        LeadStatus.CLOSED,
    }
)


class LeadPriority(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class LeadTemperature(models.TextChoices):
    HOT = "hot", "Hot"
    WARM = "warm", "Warm"
    COLD = "cold", "Cold"


class LeadSource(models.TextChoices):
    WEBSITE = "website", "Website"
    GOOGLE_MAPS = "google_maps", "Google Maps"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    REFERRAL = "referral", "Referral"
    WALK_IN = "walk_in", "Walk In"
    MANUAL = "manual", "Manual"
    OTHER = "other", "Other"


class ContactMethod(models.TextChoices):
    PHONE = "phone", "Phone"
    WHATSAPP = "whatsapp", "WhatsApp"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    EMAIL = "email", "Email"
    VISIT = "visit", "Visit"


class NextAction(models.TextChoices):
    CALL_TOMORROW = "call_tomorrow", "Call Tomorrow"
    CALL_NEXT_WEEK = "call_next_week", "Call Next Week"
    SEND_WHATSAPP = "send_whatsapp", "Send WhatsApp"
    SCHEDULE_DEMO = "schedule_demo", "Schedule Demo"
    VISIT_BRANCH = "visit_branch", "Visit Branch"
    SEND_PROPOSAL = "send_proposal", "Send Proposal"
    WAITING_CUSTOMER = "waiting_customer", "Waiting Customer"
    CLOSE_LEAD = "close_lead", "Close Lead"


class ExpectedPlan(models.TextChoices):
    """The plan sales *expects* to sell. Deliberately NOT a FK to
    ``console.Plan``: this is a forecast on an unconverted lead, so it must
    survive a plan being renamed or archived, and "Custom" has no Plan row at
    all. The real plan is chosen at conversion."""

    TRIAL = "trial", "Trial"
    BASIC = "basic", "Basic"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"
    CUSTOM = "custom", "Custom"


class CallResult(models.TextChoices):
    """The outcome of one logged call. Mirrors the call-shaped slice of
    ``LeadStatus`` — a call's result usually *becomes* the lead's status, but
    the two are separate: a call is an immutable historical record, the status
    is the lead's current state."""

    ANSWERED = "answered", "Answered"
    NO_ANSWER = "no_answer", "No Answer"
    BUSY = "busy", "Busy"
    PHONE_OFF = "phone_off", "Phone Off"
    WRONG_NUMBER = "wrong_number", "Wrong Number"
    RECEPTION_ANSWERED = "reception_answered", "Reception Answered"
    MANAGER_ANSWERED = "manager_answered", "Manager Answered"
    OWNER_ANSWERED = "owner_answered", "Owner Answered"
    CALL_BACK_LATER = "call_back_later", "Call Back Later"
    NOT_INTERESTED = "not_interested", "Not Interested"


class ActivityKind(models.TextChoices):
    """Every timeline entry's type. The console maps these to icons."""

    LEAD_CREATED = "lead_created", "Lead Created"
    WEBSITE_FORM_SUBMITTED = "website_form_submitted", "Website Form Submitted"
    MANUAL_LEAD_CREATED = "manual_lead_created", "Manual Lead Created"
    PHONE_CALL_LOGGED = "phone_call_logged", "Phone Call Logged"
    WHATSAPP_SENT = "whatsapp_sent", "WhatsApp Sent"
    EMAIL_SENT = "email_sent", "Email Sent"
    PRIORITY_CHANGED = "priority_changed", "Priority Changed"
    STATUS_CHANGED = "status_changed", "Status Changed"
    ASSIGNED_SALES_CHANGED = "assigned_sales_changed", "Assigned Sales Changed"
    DEMO_SCHEDULED = "demo_scheduled", "Demo Scheduled"
    DEMO_COMPLETED = "demo_completed", "Demo Completed"
    PROPOSAL_SENT = "proposal_sent", "Proposal Sent"
    CONVERTED_TO_MERCHANT = "converted_to_merchant", "Converted To Merchant"
    CLOSED = "closed", "Closed"
    DUPLICATE_MERGED = "duplicate_merged", "Duplicate Merged"
    NOTE_ADDED = "note_added", "Note Added"


class CrmChoiceKind(models.TextChoices):
    """Which dropdown a ``CrmChoice`` row configures."""

    STATUS = "status", "Status"
    PRIORITY = "priority", "Priority"
    TEMPERATURE = "temperature", "Temperature"
    SOURCE = "source", "Lead Source"
    CATEGORY = "category", "Business Category"
    EXPECTED_PLAN = "expected_plan", "Expected Plan"
    CONTACT_METHOD = "contact_method", "Contact Method"
    NEXT_ACTION = "next_action", "Next Action"


# The enum backing each configurable dropdown. CATEGORY is absent on purpose —
# it has no system values, so every category row is admin-created. Seeding and
# the "is this slug a system value?" check both read this map, so adding a new
# configurable dropdown means adding it here and nowhere else.
SYSTEM_CHOICES: dict[str, type[models.TextChoices]] = {
    CrmChoiceKind.STATUS: LeadStatus,
    CrmChoiceKind.PRIORITY: LeadPriority,
    CrmChoiceKind.TEMPERATURE: LeadTemperature,
    CrmChoiceKind.SOURCE: LeadSource,
    CrmChoiceKind.EXPECTED_PLAN: ExpectedPlan,
    CrmChoiceKind.CONTACT_METHOD: ContactMethod,
    CrmChoiceKind.NEXT_ACTION: NextAction,
}


def is_system_value(kind: str, slug: str) -> bool:
    """Whether ``slug`` is a code-level value of ``kind`` (so undeletable)."""
    enum = SYSTEM_CHOICES.get(kind)
    return enum is not None and slug in enum.values


# ── Lead scoring ─────────────────────────────────────────────────────────────
# Weights sum to exactly 100 at maximum (high + hot + website + demo + proposal
# + 5 calls + recent activity), so the score needs no clamping to stay in range
# and a full bar genuinely means "every signal fired".
#
# They are also tuned so a fresh website lead — medium priority, warm, one form
# submission, no calls, activity today — lands on exactly 25 (8 + 12 + 5), the
# starting score the spec calls for. That number is therefore *computed*, not
# stamped: re-scoring a brand-new website lead is a no-op rather than a jump.
_PRIORITY_POINTS: dict[str, int] = {
    LeadPriority.HIGH: 20,
    LeadPriority.MEDIUM: 8,
    LeadPriority.LOW: 3,
}
_TEMPERATURE_POINTS: dict[str, int] = {
    LeadTemperature.HOT: 25,
    LeadTemperature.WARM: 12,
    LeadTemperature.COLD: 4,
}
_WEBSITE_SUBMISSION_POINTS = 5
_DEMO_SCHEDULED_POINTS = 15
_PROPOSAL_SENT_POINTS = 15
_POINTS_PER_CALL = 2
_MAX_SCORED_CALLS = 5
_RECENT_ACTIVITY_POINTS = 10
_RECENT_ACTIVITY_WINDOW = timedelta(days=7)

# A lead's own creation is not engagement, so it must not earn the recent-
# activity points. Every lead is born with a creation entry dated now, so
# counting these would hand every new lead the bonus at birth — putting a fresh
# website lead on 35 rather than the 25 it is specified to start at, and making
# the signal mean "was created recently" instead of "is being worked".
_CREATION_KINDS: frozenset[str] = frozenset(
    {
        ActivityKind.LEAD_CREATED,
        ActivityKind.WEBSITE_FORM_SUBMITTED,
        ActivityKind.MANUAL_LEAD_CREATED,
    }
)

SCORE_MAX = 100


def score_lead(lead) -> int:
    """Recompute ``lead``'s 0-100 score from its current signals.

    Pure and idempotent: it reads the lead and its related rows and returns a
    number, so callers may run it after any mutation without worrying about
    double-counting. ``Lead.recalculate_score`` persists the result.

    Demo-scheduled and proposal-sent are read from the *activity timeline*, not
    the current status — a lead that reached "Proposal Sent" and moved on to
    "Negotiation" must keep those points, since the milestone happened.
    """
    score = 0
    score += _PRIORITY_POINTS.get(lead.priority, 0)
    score += _TEMPERATURE_POINTS.get(lead.temperature, 0)

    if lead.lead_type == LeadType.WEBSITE:
        score += _WEBSITE_SUBMISSION_POINTS

    # Unsaved lead: no related rows to count yet, and .filter() would raise.
    if lead.pk is None:
        return min(score, SCORE_MAX)

    milestones = set(
        lead.activities.filter(
            kind__in=[ActivityKind.DEMO_SCHEDULED, ActivityKind.PROPOSAL_SENT]
        ).values_list("kind", flat=True)
    )
    if ActivityKind.DEMO_SCHEDULED in milestones:
        score += _DEMO_SCHEDULED_POINTS
    if ActivityKind.PROPOSAL_SENT in milestones:
        score += _PROPOSAL_SENT_POINTS

    calls = lead.calls.count()
    score += min(calls, _MAX_SCORED_CALLS) * _POINTS_PER_CALL

    cutoff = timezone.now() - _RECENT_ACTIVITY_WINDOW
    if lead.activities.filter(created_at__gte=cutoff).exclude(kind__in=_CREATION_KINDS).exists():
        score += _RECENT_ACTIVITY_POINTS

    return min(score, SCORE_MAX)
