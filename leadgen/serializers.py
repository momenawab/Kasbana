"""Wire formats for the lead-generation console API.

Read serializers are split by weight rather than by model: the leads *table*
renders hundreds of rows and must not carry crawl payloads or raw Places JSON,
while the detail drawer wants everything. One serializer doing both would make
the list query pay for fields nobody is looking at.
"""

from __future__ import annotations

from rest_framework import serializers

from leadgen import enums
from leadgen.models import (
    AiEnrichment,
    GeneratedLead,
    JobLog,
    OwnerCandidate,
    SearchJob,
    SocialProfile,
    Verification,
    WebsiteProfile,
)


class SearchJobCreateSerializer(serializers.Serializer):
    """Validates a new search before it costs anything.

    Every constraint here exists to stop one job burning a day of Places quota:
    the radius cap, the fixed max-results set, and the business-type vocabulary.
    """

    country = serializers.CharField(max_length=2, min_length=2)
    province = serializers.CharField(max_length=120, required=False, allow_blank=True)
    city = serializers.CharField(max_length=120)
    street = serializers.CharField(max_length=200, required=False, allow_blank=True)
    radius_km = serializers.IntegerField(min_value=1, max_value=50, default=5)
    business_types = serializers.ListField(
        child=serializers.ChoiceField(choices=enums.BusinessType.choices),
        allow_empty=False,
        max_length=len(enums.BusinessType.choices),
    )
    max_results = serializers.ChoiceField(choices=enums.ALLOWED_MAX_RESULTS, default=100)
    priority = serializers.ChoiceField(
        choices=enums.JobPriority.choices, default=enums.JobPriority.NORMAL
    )


class SearchJobSerializer(serializers.ModelSerializer):
    progress_percent = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SearchJob
        fields = (
            "id",
            "country",
            "province",
            "city",
            "street",
            "radius_km",
            "business_types",
            "max_results",
            "priority",
            "status",
            "stage",
            "center_lat",
            "center_lng",
            "discovered_count",
            "duplicate_count",
            "crawled_count",
            "ready_count",
            "imported_count",
            "failed_count",
            "progress_percent",
            "started_at",
            "finished_at",
            "error",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_created_by_name(self, job: SearchJob) -> str:
        # Snapshot-free on purpose: unlike a timeline entry, a job list should
        # show who the operator *is* now, and a departed admin reads as System.
        if job.created_by is None:
            return "System"
        return job.created_by.name or job.created_by.email


class SocialProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialProfile
        fields = ("platform", "handle", "url")


class OwnerCandidateSerializer(serializers.ModelSerializer):
    """Every candidate, not just the winner — a rep checking a name needs to
    see what else was found and where each came from."""

    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = OwnerCandidate
        fields = (
            "id",
            "name",
            "role",
            "source",
            "source_display",
            "confidence",
            "evidence_url",
            "evidence_text",
            "created_at",
        )
        read_only_fields = fields


class WebsiteProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteProfile
        exclude = ("lead",)


class GeneratedLeadListSerializer(serializers.ModelSerializer):
    """The table row. Deliberately narrow — no crawl payload, no raw Places."""

    has_website = serializers.SerializerMethodField()
    has_email = serializers.SerializerMethodField()
    social_platforms = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedLead
        fields = (
            "id",
            "business_name",
            "address",
            "phone",
            "phone_e164",
            "website",
            "website_domain",
            "rating",
            "reviews_count",
            "category",
            "business_status",
            "branch_count",
            "state",
            "fit_score",
            "score_label",
            "owner_name",
            "owner_name_source",
            "owner_name_confidence",
            "crm_match",
            "crm_match_reason",
            "imported_lead",
            "imported_at",
            "duplicate_of",
            "duplicate_reason",
            "has_website",
            "has_email",
            "social_platforms",
            "google_maps_url",
            "created_at",
        )
        read_only_fields = fields

    def get_has_website(self, lead: GeneratedLead) -> bool:
        return bool(lead.website_domain)

    def get_has_email(self, lead: GeneratedLead) -> bool:
        # Reads the prefetched relation; the view must select_related it or
        # this becomes a query per row.
        profile = getattr(lead, "website_profile", None)
        return bool(profile and profile.emails)

    def get_social_platforms(self, lead: GeneratedLead) -> list[str]:
        return [social.platform for social in lead.socials.all()]


class LeadAiSerializer(serializers.ModelSerializer):
    """The drawer's AI tab. Excludes the raw payload, which the Raw tab covers."""

    class Meta:
        model = AiEnrichment
        exclude = ("raw_response", "lead")


class LeadVerificationSerializer(serializers.ModelSerializer):
    line_type_display = serializers.CharField(source="get_line_type_display", read_only=True)

    class Meta:
        model = Verification
        exclude = ("raw_response", "lead")


class GeneratedLeadDetailSerializer(GeneratedLeadListSerializer):
    """The drawer. Everything, including the raw payload behind the Raw Data tab."""

    website_profile = WebsiteProfileSerializer(read_only=True)
    socials = SocialProfileSerializer(many=True, read_only=True)
    owner_candidates = OwnerCandidateSerializer(many=True, read_only=True)
    ai_enrichment = LeadAiSerializer(read_only=True)
    verifications = LeadVerificationSerializer(many=True, read_only=True)

    class Meta(GeneratedLeadListSerializer.Meta):
        fields = GeneratedLeadListSerializer.Meta.fields + (
            "lat",
            "lng",
            "photos_count",
            "opening_hours",
            "normalized_name",
            "score_breakdown",
            "website_profile",
            "socials",
            "owner_candidates",
            "ai_enrichment",
            "verifications",
            "raw_places",
            "updated_at",
        )
        read_only_fields = fields


class JobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobLog
        fields = ("id", "stage", "level", "message", "context", "lead", "created_at")
        read_only_fields = fields


class OwnerNameSerializer(serializers.Serializer):
    """A rep recording an owner name they found themselves.

    The manual path matters: it is how a name learned on a phone call — or from
    any tool a rep uses on their own device — reaches the record, without this
    system going and taking it. Manual entries outrank everything automated and
    survive re-enrichment.
    """

    name = serializers.CharField(max_length=160)
    role = serializers.CharField(max_length=120, required=False, allow_blank=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ImportSkippedSerializer(serializers.Serializer):
    lead_id = serializers.UUIDField()
    business_name = serializers.CharField()
    reason = serializers.CharField()


class ImportResultSerializer(serializers.Serializer):
    """Declared rather than inferred so the contract states what a partial
    import returns — the skipped list is the useful half of a bulk response."""

    imported = serializers.IntegerField()
    crm_lead_ids = serializers.ListField(child=serializers.UUIDField())
    skipped = ImportSkippedSerializer(many=True)


class ImportSerializer(serializers.Serializer):
    lead_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=500
    )
    assigned_sales_id = serializers.UUIDField(required=False, allow_null=True)
    # Confirms an import past a CRM match. Not a default: the whole point of the
    # match warning is that somebody looks at it.
    force = serializers.BooleanField(default=False)


class AiEnrichmentSerializer(serializers.ModelSerializer):
    """The AI queue row and the lead drawer's AI tab.

    ``raw_response`` is excluded: it is large, it is only useful when debugging a
    specific bad answer, and the queue renders hundreds of these.
    """

    business_name = serializers.CharField(source="lead.business_name", read_only=True)
    risk_level_display = serializers.CharField(source="get_risk_level_display", read_only=True)

    class Meta:
        model = AiEnrichment
        exclude = ("raw_response",)
        read_only_fields = ("id", "created_at", "updated_at")


class VerificationSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source="lead.business_name", read_only=True)
    line_type_display = serializers.CharField(source="get_line_type_display", read_only=True)

    class Meta:
        model = Verification
        exclude = ("raw_response",)
        read_only_fields = ("id", "created_at", "updated_at")


class QueueStatsSerializer(serializers.Serializer):
    """Counts by status — the header of both queue screens."""

    queued = serializers.IntegerField()
    running = serializers.IntegerField()
    completed = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()


class ApiKeyStatusSerializer(serializers.Serializer):
    """Reports *about* a key, never its value — see leadgen.services.apikeys."""

    provider = serializers.CharField()
    label = serializers.CharField()
    purpose = serializers.CharField()
    required = serializers.BooleanField()
    env_var = serializers.CharField()
    configured = serializers.BooleanField()
    state = serializers.CharField()
    last_used_at = serializers.DateTimeField(allow_null=True)
    last_call_succeeded = serializers.BooleanField(allow_null=True)
    calls_24h = serializers.IntegerField()
    calls_30d = serializers.IntegerField()
    cost_24h_usd = serializers.DecimalField(max_digits=12, decimal_places=6)
    cost_30d_usd = serializers.DecimalField(max_digits=12, decimal_places=6)


class ProviderCostSerializer(serializers.Serializer):
    provider = serializers.CharField()
    provider_label = serializers.CharField(required=False)
    calls = serializers.IntegerField()
    cost_usd = serializers.DecimalField(max_digits=12, decimal_places=6)
    tokens_in = serializers.IntegerField(required=False)
    tokens_out = serializers.IntegerField(required=False)
    failures = serializers.IntegerField(required=False)


class DailyCostSerializer(serializers.Serializer):
    day = serializers.DateField()
    calls = serializers.IntegerField()
    cost_usd = serializers.DecimalField(max_digits=12, decimal_places=6)


class CostSummarySerializer(serializers.Serializer):
    days = serializers.IntegerField()
    total_cost_usd = serializers.DecimalField(max_digits=12, decimal_places=6)
    total_calls = serializers.IntegerField()
    total_tokens_in = serializers.IntegerField()
    total_tokens_out = serializers.IntegerField()
    leads = serializers.IntegerField()
    imported = serializers.IntegerField()
    cost_per_lead_usd = serializers.DecimalField(max_digits=12, decimal_places=6)
    cost_per_imported_usd = serializers.DecimalField(
        max_digits=12, decimal_places=6, allow_null=True
    )
    by_provider = ProviderCostSerializer(many=True)
    daily = DailyCostSerializer(many=True)
    # Surfaced so the UI can say the figures rest on configured prices rather
    # than on provider invoices.
    rates_are_estimates = serializers.BooleanField()


class StageDispatchSerializer(serializers.Serializer):
    """Whether a stage went to the broker or ran inline — the caller needs to
    know, because an inline run has already finished by the time it replies."""

    stage = serializers.CharField()
    dispatch = serializers.CharField()


class TestConnectionSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    message = serializers.CharField()


class BulkActionSerializer(serializers.Serializer):
    """A bulk operation over selected leads.

    ``lead_ids`` is capped: an unbounded bulk delete or re-run is a way to
    spend a lot of money or destroy a lot of rows with one click.
    """

    lead_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False, max_length=500
    )
    action = serializers.ChoiceField(choices=["verify", "rerun_ai", "reject", "restore", "delete"])


class BulkResultSerializer(serializers.Serializer):
    action = serializers.CharField()
    affected = serializers.IntegerField()
    dispatch = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)


class DashboardSerializer(serializers.Serializer):
    """Loose by design — the dashboard is read-only and its shape is the
    analytics module's business, not a contract other code writes against."""

    metrics = serializers.DictField()
    leads_per_day = serializers.ListField(child=serializers.DictField())
    leads_by_city = serializers.ListField(child=serializers.DictField())
    score_distribution = serializers.ListField(child=serializers.DictField())
    by_label = serializers.ListField(child=serializers.DictField())
    conversion = serializers.DictField()
    owner_sources = serializers.ListField(child=serializers.DictField())
    by_category = serializers.ListField(child=serializers.DictField())
    web_presence = serializers.DictField()
