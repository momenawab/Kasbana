"""Lead querying — the table's filters, search, sort, and the KPI cards.

Kept out of the view for the same reason ``console.merchants`` is: the filter
set is the part that grows every release, and it is far easier to test a
function that turns query params into a queryset than to test it through HTTP.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from console import crm
from console.models import Lead, LeadCall

# Columns the table may sort by. A whitelist, not ``order_by(param)``: that would
# hand any caller the ability to sort by — and therefore probe — any column on
# the model, and would 500 on a typo.
SORTABLE: frozenset[str] = frozenset(
    {
        "business_name",
        "name",
        "area",
        "priority",
        "status",
        "temperature",
        "lead_score",
        "lead_type",
        "source",
        "next_follow_up_at",
        "last_contact_at",
        "created_at",
    }
)

# Exact-match filters: query param → model field. Each accepts a repeated param
# (?status=a&status=b) and ORs the values, which is what the multi-select filter
# chips in the console send.
_EXACT_FILTERS: dict[str, str] = {
    "lead_type": "lead_type",
    "status": "status",
    "priority": "priority",
    "temperature": "temperature",
    "source": "source",
    "category": "category",
    "assigned_sales": "assigned_sales_id",
}


def lead_queryset() -> QuerySet[Lead]:
    """The base queryset every lead read starts from. ``select_related`` is not
    an optimisation detail here — the table serialises both admins on every row,
    so without it a 50-row page costs 100 extra queries."""
    return Lead.objects.select_related("assigned_sales", "created_by", "converted_merchant")


def _today_bounds() -> tuple[datetime, datetime]:
    """Midnight-to-midnight in the *operator's* timezone, not UTC's. A Cairo
    sales team opening the board at 01:00 must see the calls they are about to
    make, not yesterday's."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(timezone.localtime().date(), time.min), tz)
    return start, start + timedelta(days=1)


# The two follow-up predicates, defined once because both the KPI cards and the
# table's filter bar must mean the same thing by them. When a card reads
# "Overdue 3" and clicking it lists five rows, the number is not just unhelpful,
# it is evidence the board cannot be trusted — so the count and the drill-down
# are built from the same Q object rather than two hand-matched queries.
def overdue_q() -> Q:
    """Follow-up date passed, on a lead still worth chasing. Terminal leads are
    excluded: a lead that said "do not call again" is not an overdue task."""
    return Q(next_follow_up_at__lt=timezone.now()) & ~Q(status__in=crm.TERMINAL_STATUSES)


def follow_up_today_q() -> Q:
    start, end = _today_bounds()
    return Q(next_follow_up_at__gte=start, next_follow_up_at__lt=end)


def _parse_date(value: str) -> datetime | None:
    """Parse a ``YYYY-MM-DD`` filter bound into an aware datetime, or None if it
    is not one.

    Unparseable input filters nothing rather than raising: a filter bar is not a
    place to punish a typo, and "17/07/2026" is a date-shaped string a person
    will genuinely type. Length-checking is not enough — that string is ten
    characters long and would still blow up strptime.
    """
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return timezone.make_aware(parsed, timezone.get_current_timezone())


def apply_filters(qs: QuerySet[Lead], params) -> QuerySet[Lead]:
    """Narrow ``qs`` by the table's filter bar.

    Unknown params are ignored, and an empty value is treated as "no filter" —
    the console sends ``?status=`` when a user clears a chip, and that must mean
    all statuses, not no leads.
    """
    for param, field in _EXACT_FILTERS.items():
        values = [v for v in params.getlist(param) if v]
        if values:
            qs = qs.filter(**{f"{field}__in": values})

    # Unassigned is a first-class filter — it is the "who is not working these?"
    # question — and cannot be expressed by ?assigned_sales=<id>.
    if params.get("unassigned") in ("1", "true"):
        qs = qs.filter(assigned_sales__isnull=True)

    # The two follow-up views the KPI cards drill into. Same predicates the cards
    # count with, so the number on the card and the rows behind it always agree.
    if params.get("overdue") in ("1", "true"):
        qs = qs.filter(overdue_q())
    if params.get("follow_up") == "today":
        qs = qs.filter(follow_up_today_q())

    if area := params.get("area", "").strip():
        qs = qs.filter(area__icontains=area)

    for param, field in (
        ("created_from", "created_at__gte"),
        ("created_to", "created_at__lt"),
        ("follow_up_from", "next_follow_up_at__gte"),
        ("follow_up_to", "next_follow_up_at__lt"),
    ):
        raw = params.get(param, "").strip()
        if not raw:
            continue
        bound = _parse_date(raw)
        if bound is None:
            continue
        # "_to" is inclusive of the whole day the user picked — they mean "up to
        # and including the 5th", not "up to midnight as the 5th begins".
        if param.endswith("_to"):
            bound += timedelta(days=1)
        qs = qs.filter(**{field: bound})

    if q := params.get("q", "").strip():
        qs = qs.filter(
            Q(business_name__icontains=q)
            | Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(whatsapp__icontains=q)
            | Q(email__icontains=q)
            | Q(area__icontains=q)
        )

    return qs


def apply_sort(qs: QuerySet[Lead], params) -> tuple[QuerySet[Lead], tuple[str, ...]]:
    """Order ``qs`` by ``?sort=`` (prefix ``-`` for descending), defaulting to
    newest first. Returns the ordering too, because cursor pagination needs to
    be told the same thing the queryset was.

    Always tie-breaks on ``-created_at``: cursor pagination walks the ordering
    to find its place, so a sort on a non-unique column (every lead is "medium"
    priority) without a unique tiebreak can skip or repeat rows across pages.
    """
    raw = params.get("sort", "").strip()
    field = raw.lstrip("-")
    if not field or field not in SORTABLE:
        return qs.order_by("-created_at"), ("-created_at",)

    ordering: tuple[str, ...] = (raw,) if field == "created_at" else (raw, "-created_at")
    return qs.order_by(*ordering), ordering


def kpis(qs: QuerySet[Lead] | None = None) -> dict:
    """The dashboard cards, in one query plus two.

    Computed over the *filtered* queryset the caller passes, so the cards
    describe what the table below them is showing rather than contradicting it.
    """
    qs = lead_queryset() if qs is None else qs
    today_start, today_end = _today_bounds()

    counts = qs.aggregate(
        total=Count("id"),
        website=Count("id", filter=Q(lead_type=crm.LeadType.WEBSITE)),
        manual=Count("id", filter=Q(lead_type=crm.LeadType.MANUAL)),
        interested=Count("id", filter=Q(status=crm.LeadStatus.INTERESTED)),
        demo_scheduled=Count("id", filter=Q(status=crm.LeadStatus.DEMO_SCHEDULED)),
        customers=Count(
            "id", filter=Q(status__in=[crm.LeadStatus.CUSTOMER, crm.LeadStatus.CONVERTED])
        ),
        converted=Count("id", filter=Q(converted_merchant__isnull=False)),
        follow_ups_today=Count("id", filter=follow_up_today_q()),
        overdue_follow_ups=Count("id", filter=overdue_q()),
    )

    total = counts["total"]
    converted = counts.pop("converted")
    counts["calls_today"] = LeadCall.objects.filter(
        lead__in=qs, called_at__gte=today_start, called_at__lt=today_end
    ).count()
    counts["conversion_rate"] = round(converted / total * 100, 1) if total else 0.0
    return counts
