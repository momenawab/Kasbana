"""Tests for AI enrichment.

The behaviour worth protecting is scepticism. A model's output reaches columns a
rep reads as fact, so the parser's job is to refuse anything it cannot trust —
without discarding an analysis we have already paid for.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from leadgen import enums
from leadgen.glm import GlmError, GlmResult, extract_json
from leadgen.models import AiEnrichment, ApiUsage, GeneratedLead, SearchJob, WebsiteProfile
from leadgen.services import ai

pytestmark = pytest.mark.django_db


GOOD = {
    "business_summary": "A busy speciality coffee bar in Maadi.",
    "target_customers": "Young professionals and students",
    "estimated_size": "small",
    "estimated_daily_visitors": 180,
    "estimated_monthly_customers": 5400,
    "estimated_revenue_range": "EGP 300k-500k / month",
    "business_model": "independent",
    "is_franchise": False,
    "is_premium": True,
    "estimated_branches": 1,
    "likelihood_uses_pos": 70,
    "likelihood_uses_loyalty": 20,
    "likelihood_accepts_digital": 80,
    "recommended_pitch": "Reward the regulars you already have.",
    "recommended_plan": "growth",
    "risk_level": "low",
    "confidence": 72,
}


class FakeGlm:
    """Returns a queued payload, or raises what it was given."""

    def __init__(self, data=None, raises=None, tokens=(500, 200)):
        self.data = data if data is not None else dict(GOOD)
        self.raises = raises
        self.tokens = tokens
        self.calls = 0
        self.last_user_prompt = ""

    def complete_json(self, *, system, user, max_tokens=1200):
        self.calls += 1
        self.last_user_prompt = user
        if self.raises:
            raise self.raises
        return GlmResult(
            data=self.data,
            tokens_in=self.tokens[0],
            tokens_out=self.tokens[1],
            duration_ms=900,
            model="glm-5.2",
            raw={"choices": [{"message": {"content": "{}"}}]},
        )


def make_lead(**overrides) -> GeneratedLead:
    job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
    defaults = {
        "place_id": "p1",
        "business_name": "Karam Cafe",
        "business_status": "OPERATIONAL",
        "reviews_count": 900,
    }
    return GeneratedLead.objects.create(job=job, **{**defaults, **overrides})


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_tolerates_a_code_fence(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_prose_is_a_failure_not_an_empty_result(self):
        """A model that answered in prose has not answered. Letting it through
        would write blank analysis rows that look like real ones."""
        with pytest.raises(GlmError, match="valid JSON"):
            extract_json("Sure! Here is my analysis of the business.")

    def test_a_json_array_is_rejected(self):
        with pytest.raises(GlmError, match="expected a JSON object"):
            extract_json("[1, 2, 3]")

    def test_empty_response_is_rejected(self):
        with pytest.raises(GlmError, match="empty"):
            extract_json("   ")


class TestCoercion:
    def test_clean_payload_passes_through(self):
        parsed = ai.parse_analysis(GOOD)
        assert parsed["estimated_daily_visitors"] == 180
        assert parsed["risk_level"] == enums.RiskLevel.LOW
        assert parsed["is_premium"] is True

    def test_hallucinated_magnitudes_are_clamped(self):
        """8 million daily visitors at a Maadi cafe must never reach a rep."""
        parsed = ai.parse_analysis({**GOOD, "estimated_daily_visitors": 8_000_000})
        assert parsed["estimated_daily_visitors"] == ai.MAX_DAILY_VISITORS

    def test_unparseable_number_becomes_null_not_zero(self):
        """Zero would read as a measured finding of none; null says we do not
        know, which is the truth."""
        parsed = ai.parse_analysis({**GOOD, "estimated_daily_visitors": "lots"})
        assert parsed["estimated_daily_visitors"] is None

    def test_numeric_string_and_float_are_accepted(self):
        assert (
            ai.parse_analysis({**GOOD, "estimated_daily_visitors": "180"})[
                "estimated_daily_visitors"
            ]
            == 180
        )
        assert (
            ai.parse_analysis({**GOOD, "estimated_daily_visitors": 180.0})[
                "estimated_daily_visitors"
            ]
            == 180
        )

    def test_negative_numbers_are_rejected(self):
        assert ai.parse_analysis({**GOOD, "estimated_branches": -3})["estimated_branches"] is None

    def test_percentages_are_clamped_to_100(self):
        assert ai.parse_analysis({**GOOD, "likelihood_uses_pos": 500})["likelihood_uses_pos"] == 100

    def test_value_outside_the_enum_becomes_empty(self):
        parsed = ai.parse_analysis({**GOOD, "risk_level": "catastrophic"})
        assert parsed["risk_level"] == ""

    def test_booleans_survive_string_forms(self):
        assert ai.parse_analysis({**GOOD, "is_franchise": "yes"})["is_franchise"] is True
        assert ai.parse_analysis({**GOOD, "is_franchise": "maybe"})["is_franchise"] is None

    def test_one_bad_field_does_not_discard_the_analysis(self):
        """We have already paid for this call — salvage what is usable."""
        parsed = ai.parse_analysis({**GOOD, "confidence": "very high"})
        assert parsed["confidence"] is None
        assert parsed["business_summary"] == GOOD["business_summary"]

    def test_missing_payload_yields_empty_not_an_exception(self):
        parsed = ai.parse_analysis({})
        assert parsed["business_summary"] == ""
        assert parsed["estimated_daily_visitors"] is None


class TestPrompt:
    def test_absent_website_is_stated_as_absent(self):
        """Saying nothing about a website invites the model to assume one."""
        prompt = ai.build_user_prompt(make_lead())
        assert "none of its own" in prompt

    def test_platform_link_is_explained_not_presented_as_a_site(self):
        lead = make_lead(website="https://instagram.com/karam", website_domain="")
        assert "social or marketplace page" in ai.build_user_prompt(lead)

    def test_crawled_findings_are_included(self):
        lead = make_lead(website="https://karam.com.eg", website_domain="karam.com.eg")
        WebsiteProfile.objects.create(
            lead=lead, pos_vendors=["foodics"], meta_description="Speciality coffee"
        )
        lead.refresh_from_db()
        prompt = ai.build_user_prompt(lead)
        assert "foodics" in prompt
        assert "Speciality coffee" in prompt

    def test_a_lead_with_a_category_builds_a_prompt(self):
        """Regression: every real lead has a category, but the original tests
        all left it empty, so a broken category lookup passed unnoticed until
        the exports hit the same field."""
        lead = make_lead(category=enums.BusinessType.COFFEE_SHOP)
        assert "Coffee Shop" in ai.build_user_prompt(lead)

    def test_an_unrecognised_category_does_not_break_the_prompt(self):
        lead = make_lead(category="something_new")
        assert "something_new" in ai.build_user_prompt(lead)

    def test_the_model_is_never_asked_to_name_a_person(self):
        """The most dangerous thing this pipeline could invent."""
        assert "Never name a person" in ai.SYSTEM_PROMPT
        assert "owner" not in ai.OUTPUT_SCHEMA.lower()


class TestEnrich:
    def test_stores_the_analysis_and_prices_the_call(self):
        lead = make_lead()
        client = FakeGlm(tokens=(1000, 500))

        record = ai.enrich(lead, client=client)

        assert record.status == enums.TaskStatus.COMPLETED
        assert record.business_summary == GOOD["business_summary"]
        assert record.tokens_in == 1000 and record.tokens_out == 500
        assert record.cost_usd > 0
        assert record.model == "glm-5.2"

    def test_writes_a_usage_row_for_the_cost_ledger(self):
        lead = make_lead()
        ai.enrich(lead, client=FakeGlm())

        usage = ApiUsage.objects.get(provider=enums.ApiProvider.GLM)
        assert usage.lead_id == lead.id
        assert usage.job_id == lead.job_id
        assert usage.succeeded is True

    def test_closed_business_is_skipped_without_paying(self):
        lead = make_lead(business_status="CLOSED_PERMANENTLY")
        client = FakeGlm()

        record = ai.enrich(lead, client=client)

        assert record.status == enums.TaskStatus.SKIPPED
        assert client.calls == 0
        assert not ApiUsage.objects.exists()

    def test_a_model_failure_is_recorded_not_raised(self):
        """An outage must not fail the job — the lead keeps its fit score."""
        lead = make_lead()
        record = ai.enrich(lead, client=FakeGlm(raises=GlmError("upstream is down")))

        assert record.status == enums.TaskStatus.FAILED
        assert "upstream is down" in record.error

    def test_a_failed_call_is_still_counted_as_usage(self):
        """Providers charge for most failures; under-counting spend is worse
        than over-counting it."""
        lead = make_lead()
        ai.enrich(lead, client=FakeGlm(raises=GlmError("boom")))

        usage = ApiUsage.objects.get(provider=enums.ApiProvider.GLM)
        assert usage.succeeded is False

    def test_bad_json_fails_the_row_rather_than_writing_nonsense(self):
        lead = make_lead()
        record = ai.enrich(lead, client=FakeGlm(raises=GlmError("did not return valid JSON")))

        assert record.status == enums.TaskStatus.FAILED
        assert record.business_summary == ""

    def test_re_running_replaces_rather_than_accumulating(self):
        lead = make_lead()
        ai.enrich(lead, client=FakeGlm())
        ai.enrich(lead, client=FakeGlm())

        assert AiEnrichment.objects.filter(lead=lead).count() == 1
        assert AiEnrichment.objects.get(lead=lead).attempts == 2

    def test_cost_is_computed_from_real_token_counts(self):
        result = GlmResult(data={}, tokens_in=1_000_000, tokens_out=0)
        from django.conf import settings

        assert result.cost_usd == Decimal(str(settings.GLM_PRICE_PER_MTOK_IN)).quantize(
            Decimal("0.000001")
        )
