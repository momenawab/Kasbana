"""Lead-generation persistence.

These models live in ``leadgen`` rather than ``core`` because they are not part
of the frozen tenant schema (contract §3.4): nothing here belongs to a merchant,
and a discovered business is not yet a Stampn record of anything. The boundary
is ``GeneratedLead.imported_lead`` — the single FK where prospecting hands over
to the CRM, and the only place these tables touch ``console``.

Table names follow the ``lead_generation_*`` convention from the spec so the
module reads the same in psql as it does in code.

FK direction note: ``GeneratedLead`` points at ``console.Lead`` and never the
reverse. Prospecting knows about the CRM; the CRM does not know it was
prospected, so deleting this whole app would leave the CRM intact.
"""

from __future__ import annotations

from django.db import models

from core.models import TimeStampedModel, UUIDModel
from leadgen import enums


class SearchJob(UUIDModel, TimeStampedModel):
    """One "find me businesses like this, here" request and its progress.

    Counters are denormalised rather than derived. The jobs list shows six of
    them per row, and computing them from ``GeneratedLead`` would be six
    aggregate queries per job on every poll of a live-updating table. Stages
    own their own counter and only ever increment it, so a partial job reports
    honestly rather than reporting zero until it finishes.
    """

    # ── What to search ───────────────────────────────────────────────────────
    country = models.CharField(max_length=2)  # ISO 3166-1 alpha-2, e.g. "EG"
    province = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    street = models.CharField(max_length=200, blank=True)
    radius_km = models.PositiveSmallIntegerField(default=5)
    # A list of ``enums.BusinessType`` values. JSON rather than a join table:
    # it is a fixed-vocabulary multi-select that is only ever read as a whole,
    # written once at creation, and never queried by element.
    business_types = models.JSONField(default=list)
    max_results = models.PositiveIntegerField(default=100)

    # Geocoded from the address fields at creation so the Places calls have a
    # centre. Null means geocoding has not run or failed — the job cannot start
    # without them, which ``leadgen.services.jobs`` enforces.
    center_lat = models.FloatField(null=True, blank=True)
    center_lng = models.FloatField(null=True, blank=True)

    # ── Execution ────────────────────────────────────────────────────────────
    priority = models.CharField(
        max_length=16, choices=enums.JobPriority.choices, default=enums.JobPriority.NORMAL
    )
    status = models.CharField(
        max_length=16, choices=enums.JobStatus.choices, default=enums.JobStatus.QUEUED
    )
    stage = models.CharField(max_length=24, choices=enums.PipelineStage.choices, blank=True)

    # ── Progress ─────────────────────────────────────────────────────────────
    discovered_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    crawled_count = models.PositiveIntegerField(default=0)
    ready_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Operator-facing failure summary. The stack trace goes to JobLog; this is
    # the one line the jobs table shows, so it must stay readable.
    error = models.CharField(max_length=500, blank=True)

    created_by = models.ForeignKey(
        "console.AdminUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadgen_jobs",
    )

    class Meta:
        db_table = "lead_generation_jobs"
        ordering = ["-created_at"]
        indexes = [
            # The jobs list filters by status; the worker claims by status+priority.
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["created_by"]),
        ]

    def __str__(self) -> str:
        return f"job({self.city} · {len(self.business_types)} types · {self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in enums.TERMINAL_JOB_STATUSES

    @property
    def progress_percent(self) -> int:
        """Rough completion for the progress bar, 0-100.

        Deliberately based on discovered-vs-target rather than stage weights:
        it is the only quantity known up front. Stage weights would need a
        per-stage cost model that changes with how many businesses have
        websites, and a bar that jumps backwards is worse than a coarse one.
        """
        if self.is_terminal:
            return 100
        if not self.max_results:
            return 0
        return min(100, round(self.discovered_count / self.max_results * 100))


class GeneratedLead(UUIDModel, TimeStampedModel):
    """One business discovered by a job, at whatever enrichment depth it reached.

    A row appears the moment Places returns it and is enriched in place, so a
    running job's results are browsable immediately rather than materialising
    at the end.

    ``place_id`` is unique per job, not globally: the same cafe legitimately
    turns up in a Cairo sweep and a Giza sweep, and each job's results should
    be self-contained. Cross-job duplicates are surfaced by the CRM match
    stage, which is where the question actually matters.
    """

    job = models.ForeignKey(SearchJob, on_delete=models.CASCADE, related_name="leads")

    # ── Google Places payload ────────────────────────────────────────────────
    place_id = models.CharField(max_length=255)
    business_name = models.CharField(max_length=255)
    # Casefolded, punctuation- and diacritic-stripped, Arabic normalised
    # (see ``leadgen.dedupe.normalize_name``). Stored rather than computed so
    # the similar-name pass is an indexed lookup instead of a table scan.
    normalized_name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=500, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    # E.164 via libphonenumber, parsed against the job's country. The raw
    # ``phone`` is kept beside it because Places formats inconsistently and the
    # original is what a rep sees if parsing failed.
    phone_e164 = models.CharField(max_length=24, blank=True)
    website = models.URLField(max_length=500, blank=True)
    # Registrable domain, lowercased, ``www.`` stripped — the dedupe key.
    # Two branches sharing one site are one business for our purposes.
    website_domain = models.CharField(max_length=253, blank=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    reviews_count = models.PositiveIntegerField(default=0)
    photos_count = models.PositiveIntegerField(default=0)
    business_status = models.CharField(max_length=32, blank=True)  # OPERATIONAL, CLOSED_*
    category = models.CharField(max_length=64, blank=True)  # our BusinessType value
    opening_hours = models.JSONField(default=dict, blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True)

    # ── Enrichment state ─────────────────────────────────────────────────────
    state = models.CharField(
        max_length=16, choices=enums.LeadState.choices, default=enums.LeadState.DISCOVERED
    )

    # ── Owner resolution ─────────────────────────────────────────────────────
    # The winning candidate, denormalised from OwnerCandidate so the leads table
    # renders without a join. Empty is a legitimate, common outcome — see the
    # OwnerCandidate docstring for why we do not fall back to a guess.
    owner_name = models.CharField(max_length=160, blank=True)
    owner_name_source = models.CharField(
        max_length=24, choices=enums.OwnerNameSource.choices, blank=True
    )
    owner_name_confidence = models.CharField(
        max_length=8, choices=enums.Confidence.choices, blank=True
    )

    # ── Scoring ──────────────────────────────────────────────────────────────
    # Fit, not engagement. See leadgen.scoring — this must never be written to
    # console.Lead.lead_score, which measures how hard a rep has worked a lead
    # and is recomputed from the CRM timeline on every activity.
    fit_score = models.PositiveSmallIntegerField(default=0)
    score_label = models.CharField(max_length=8, choices=enums.ScoreLabel.choices, blank=True)
    # Every signal that fired and what it contributed, so a rep disputing a
    # score gets an itemised answer instead of a number.
    score_breakdown = models.JSONField(default=list, blank=True)

    # ── Deduplication ────────────────────────────────────────────────────────
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates"
    )
    duplicate_reason = models.CharField(
        max_length=24, choices=enums.DedupeReason.choices, blank=True
    )
    # How many listings collapsed into this one, itself included. A chain's
    # branches are absorbed rather than discarded (see leadgen.dedupe): selling
    # to Cilantro is one conversation with a head office, and the branch count
    # is precisely the "multiple branches" signal the score rewards.
    branch_count = models.PositiveSmallIntegerField(default=1)

    # ── CRM handover ─────────────────────────────────────────────────────────
    # A pre-existing CRM record matching this business. Set by the CRM-match
    # stage and used to warn before import; it does not block one, because a
    # match on phone alone is often a shared landline across a food court.
    crm_match = models.ForeignKey(
        "console.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadgen_matches",
    )
    crm_match_reason = models.CharField(max_length=24, blank=True)
    # The CRM lead this row created. Distinct from crm_match: that is what we
    # found, this is what we made. Both set means we merged into an existing one.
    imported_lead = models.ForeignKey(
        "console.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadgen_origins",
    )
    imported_at = models.DateTimeField(null=True, blank=True)

    # Verbatim Places response. Kept because the Raw Data tab is the only way
    # to answer "where did this field come from" when a mapping looks wrong,
    # and because re-running enrichment must not require re-paying for the call.
    raw_places = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lead_generation_leads"
        ordering = ["-fit_score", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "place_id"], name="uniq_leadgen_lead_job_place"
            ),
        ]
        indexes = [
            # The results table: filter by job, sort by score.
            models.Index(fields=["job", "-fit_score"]),
            models.Index(fields=["job", "state"]),
            # Dedupe probes these three within a job.
            models.Index(fields=["job", "phone_e164"]),
            models.Index(fields=["job", "website_domain"]),
            models.Index(fields=["job", "normalized_name"]),
            # Cross-job "have we seen this business before" and CRM matching.
            models.Index(fields=["place_id"]),
            models.Index(fields=["score_label"]),
        ]

    def __str__(self) -> str:
        return f"leadgen({self.business_name} · {self.fit_score})"

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of_id is not None


class WebsiteProfile(UUIDModel, TimeStampedModel):
    """What the crawl found on a business's own website.

    Split from ``GeneratedLead`` rather than inlined: only businesses with a
    website get a row (a large minority here), the payload is wide and mostly
    text, and the leads table never selects any of it. Keeping it separate
    means the list query stays narrow.

    Everything here comes from pages the business publishes about itself, which
    is why it is both reliable and unproblematic to store.
    """

    lead = models.OneToOneField(
        GeneratedLead, on_delete=models.CASCADE, related_name="website_profile"
    )

    fetched_at = models.DateTimeField(null=True, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    # Empty when the fetch succeeded. A crawl failure is not a lead failure —
    # the business still scores on its Places signals.
    error = models.CharField(max_length=300, blank=True)
    pages_crawled = models.PositiveSmallIntegerField(default=0)

    # ── Contact ──────────────────────────────────────────────────────────────
    emails = models.JSONField(default=list, blank=True)
    phones = models.JSONField(default=list, blank=True)

    # ── Identity ─────────────────────────────────────────────────────────────
    logo_url = models.URLField(max_length=500, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)
    about_text = models.TextField(blank=True)
    # Named on the privacy policy or terms page. The most reliable string on
    # any site: those pages are legally obliged to identify the operator.
    legal_entity = models.CharField(max_length=255, blank=True)

    # ── Commercial signals ───────────────────────────────────────────────────
    menu_urls = models.JSONField(default=list, blank=True)
    reservation_platforms = models.JSONField(default=list, blank=True)
    delivery_platforms = models.JSONField(default=list, blank=True)
    technologies = models.JSONField(default=list, blank=True)
    payment_providers = models.JSONField(default=list, blank=True)
    # Detected from page markup — a loyalty widget or POS script means the
    # business already solved this problem, which the score treats as a
    # negative signal rather than a positive one.
    pos_vendors = models.JSONField(default=list, blank=True)
    loyalty_vendors = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "lead_generation_website"

    def __str__(self) -> str:
        return f"website({self.lead_id})"


class SocialProfile(UUIDModel, TimeStampedModel):
    """A social account the business links to from its own site.

    One row per platform. Detection only: handle and URL, no follower counts or
    activity dates. Those would require crawling Meta/TikTok, which they block
    and prohibit — a column for them would be null in production and would drag
    down any score that trusted it.
    """

    lead = models.ForeignKey(GeneratedLead, on_delete=models.CASCADE, related_name="socials")
    platform = models.CharField(max_length=16, choices=enums.SocialPlatform.choices)
    handle = models.CharField(max_length=160, blank=True)
    url = models.URLField(max_length=500)

    class Meta:
        db_table = "lead_generation_social"
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "platform"], name="uniq_leadgen_social_lead_platform"
            ),
        ]
        indexes = [models.Index(fields=["lead", "platform"])]

    def __str__(self) -> str:
        return f"social({self.platform} · {self.handle or self.url})"


class OwnerCandidate(UUIDModel, TimeStampedModel):
    """A possible owner/decision-maker name, with its provenance.

    Every candidate is kept, not just the winner, because a rep about to open a
    call needs to see *why* we think this is the owner. "Ahmed Karam — named on
    the privacy policy" earns a different opening line than "Ahmed — guessed
    from ahmed@…", and an unattributed string invites a rep to use a name that
    is wrong.

    Nothing here is ever fabricated: when no source fires, the lead imports with
    no owner name and a next action of identifying the decision-maker. A
    thirty-second question on the first call beats a confident guess.
    """

    lead = models.ForeignKey(
        GeneratedLead, on_delete=models.CASCADE, related_name="owner_candidates"
    )
    name = models.CharField(max_length=160)
    role = models.CharField(max_length=120, blank=True)  # as published, e.g. "Founder"
    source = models.CharField(max_length=24, choices=enums.OwnerNameSource.choices)
    confidence = models.CharField(max_length=8, choices=enums.Confidence.choices)
    # The page or field the name was read from, so the claim is checkable.
    evidence_url = models.URLField(max_length=500, blank=True)
    evidence_text = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "lead_generation_owner_candidates"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["lead"])]

    def __str__(self) -> str:
        return f"owner({self.name} · {self.source})"


class JobLog(UUIDModel, TimeStampedModel):
    """Append-only operator log for one job.

    Separate from ``AdminAuditLog``, which answers "which operator did what" for
    compliance. This answers "what did the pipeline do and why did it stall",
    and most of its entries have no human actor at all.

    ``lead`` is nullable because stage-level lines (a Places page fetched, a
    stage starting) belong to the job rather than to any one business.
    """

    job = models.ForeignKey(SearchJob, on_delete=models.CASCADE, related_name="logs")
    lead = models.ForeignKey(
        GeneratedLead, null=True, blank=True, on_delete=models.CASCADE, related_name="logs"
    )
    stage = models.CharField(max_length=24, choices=enums.PipelineStage.choices, blank=True)
    level = models.CharField(
        max_length=8, choices=enums.LogLevel.choices, default=enums.LogLevel.INFO
    )
    message = models.CharField(max_length=500)
    # Structured detail — retry counts, HTTP status, the exception class. Read
    # by humans debugging, never queried, so JSON rather than columns.
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lead_generation_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job", "-created_at"]),
            models.Index(fields=["job", "level"]),
            models.Index(fields=["lead"]),
        ]

    def __str__(self) -> str:
        return f"log({self.level} · {self.message[:60]})"


class AiEnrichment(UUIDModel, TimeStampedModel):
    """What the model concluded about one business, plus what it cost.

    One row per lead, replaced on re-run. Both the parsed fields and the raw
    response are kept: the parsed columns are what the UI and any future
    scoring read, and the raw payload is the only way to tell a bad prompt from
    a bad parse when a field looks wrong.

    Every estimate is stored as an estimate. ``estimated_monthly_customers`` is
    a model's guess from a Places listing and a website, not a measurement, and
    the UI labels it that way — a number that looks like data but is a guess is
    how a rep ends up quoting it to a prospect.
    """

    lead = models.OneToOneField(
        GeneratedLead, on_delete=models.CASCADE, related_name="ai_enrichment"
    )

    status = models.CharField(
        max_length=16, choices=enums.TaskStatus.choices, default=enums.TaskStatus.QUEUED
    )
    # The exact model string, not a friendly name: reproducing or disputing an
    # output a month later needs to know which model produced it.
    model = models.CharField(max_length=64, blank=True)
    prompt_version = models.CharField(max_length=16, blank=True)

    # ── The analysis ─────────────────────────────────────────────────────────
    business_summary = models.TextField(blank=True)
    target_customers = models.CharField(max_length=500, blank=True)
    estimated_size = models.CharField(max_length=64, blank=True)
    estimated_daily_visitors = models.PositiveIntegerField(null=True, blank=True)
    estimated_monthly_customers = models.PositiveIntegerField(null=True, blank=True)
    estimated_revenue_range = models.CharField(max_length=120, blank=True)
    business_model = models.CharField(max_length=64, blank=True)  # franchise/independent/chain
    is_franchise = models.BooleanField(null=True, blank=True)
    is_premium = models.BooleanField(null=True, blank=True)
    estimated_branches = models.PositiveSmallIntegerField(null=True, blank=True)

    # 0-100 likelihoods. Integers rather than floats: the model is guessing, and
    # rendering 73.4% would imply a precision that is not there.
    likelihood_uses_pos = models.PositiveSmallIntegerField(null=True, blank=True)
    likelihood_uses_loyalty = models.PositiveSmallIntegerField(null=True, blank=True)
    likelihood_accepts_digital = models.PositiveSmallIntegerField(null=True, blank=True)

    recommended_pitch = models.TextField(blank=True)
    recommended_plan = models.CharField(max_length=64, blank=True)
    risk_level = models.CharField(max_length=8, choices=enums.RiskLevel.choices, blank=True)
    confidence = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-100

    # ── Cost and diagnostics ─────────────────────────────────────────────────
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lead_generation_ai"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),  # the AI queue screen
            models.Index(fields=["lead"]),
        ]

    def __str__(self) -> str:
        return f"ai({self.lead_id} · {self.status})"


class Verification(UUIDModel, TimeStampedModel):
    """One phone or email checked against a provider.

    Separate rows per contact rather than columns on the lead: a business often
    publishes several numbers and addresses, and "which of these actually
    reaches someone" is the question a rep needs answered.

    Note what is deliberately absent: no owner name, no spam-report count, no
    "likely manager". Those come from crowd-sourced caller-ID databases with no
    lawful API, and inventing columns for data we will not collect would leave
    them null in production while implying we tried.
    """

    lead = models.ForeignKey(
        GeneratedLead, on_delete=models.CASCADE, related_name="verifications"
    )
    kind = models.CharField(max_length=8, choices=enums.VerificationKind.choices)
    # The number or address as checked — E.164 for phones, lowercased for email.
    target = models.CharField(max_length=254)

    status = models.CharField(
        max_length=16, choices=enums.TaskStatus.choices, default=enums.TaskStatus.QUEUED
    )
    result = models.CharField(
        max_length=16, choices=enums.VerificationResult.choices, blank=True
    )
    provider = models.CharField(max_length=24, choices=enums.ApiProvider.choices, blank=True)

    # ── Phone findings ───────────────────────────────────────────────────────
    line_type = models.CharField(
        max_length=16, choices=enums.PhoneLineType.choices, blank=True
    )
    carrier = models.CharField(max_length=120, blank=True)

    # ── Email findings ───────────────────────────────────────────────────────
    deliverable = models.BooleanField(null=True, blank=True)
    is_disposable = models.BooleanField(null=True, blank=True)
    is_role_address = models.BooleanField(null=True, blank=True)
    domain_valid = models.BooleanField(null=True, blank=True)

    confidence = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-100
    credits_used = models.PositiveIntegerField(default=0)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "lead_generation_verification"
        ordering = ["-created_at"]
        constraints = [
            # One verification per contact per lead — re-running updates in place
            # rather than accumulating a row per attempt, so a retried queue does
            # not multiply its own backlog.
            models.UniqueConstraint(
                fields=["lead", "kind", "target"], name="uniq_leadgen_verification_target"
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"]),  # the verification queue
            models.Index(fields=["lead", "kind"]),
            models.Index(fields=["result"]),
        ]

    def __str__(self) -> str:
        return f"verify({self.kind} · {self.target} · {self.result or self.status})"


class ApiUsage(UUIDModel, TimeStampedModel):
    """One billed interaction with a paid third party.

    The ledger behind cost-per-lead. Written per call rather than aggregated
    nightly because the question operators actually ask — "why did yesterday
    cost that much" — needs the individual calls, and because an aggregate that
    drifts from reality is worse than no aggregate.

    ``job`` and ``lead`` are nullable: a geocode belongs to a job but no lead,
    and a Test Connection belongs to neither.
    """

    provider = models.CharField(max_length=24, choices=enums.ApiProvider.choices)
    operation = models.CharField(max_length=64)  # e.g. "searchText", "chat.completions"

    job = models.ForeignKey(
        SearchJob, null=True, blank=True, on_delete=models.SET_NULL, related_name="api_usage"
    )
    lead = models.ForeignKey(
        GeneratedLead, null=True, blank=True, on_delete=models.SET_NULL, related_name="api_usage"
    )

    calls = models.PositiveIntegerField(default=1)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    # Six decimal places: a single GLM call can cost a fraction of a cent, and
    # rounding to cents per row would lose most of the spend across a job.
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    succeeded = models.BooleanField(default=True)

    class Meta:
        db_table = "lead_generation_api_usage"
        ordering = ["-created_at"]
        indexes = [
            # The cost dashboard slices by provider over a date range.
            models.Index(fields=["provider", "-created_at"]),
            models.Index(fields=["job"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return f"usage({self.provider} · {self.operation} · ${self.cost_usd})"
