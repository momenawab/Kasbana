"""Tests for lead-generation fit scoring.

The properties worth protecting are the ones a rep would notice: a dead business
never outranks a live one, the breakdown explains every point, and nothing
reaches Hot on signals we have not verified.
"""

from __future__ import annotations

import pytest

from leadgen import enums, scoring
from leadgen.models import GeneratedLead, SearchJob, SocialProfile, WebsiteProfile

pytestmark = pytest.mark.django_db


def make_job() -> SearchJob:
    return SearchJob.objects.create(country="EG", city="Cairo", max_results=100)


def make_lead(**overrides) -> GeneratedLead:
    defaults = {
        "job": make_job(),
        "place_id": "place-1",
        "business_name": "Karam Cafe",
        "business_status": "OPERATIONAL",
    }
    return GeneratedLead.objects.create(**{**defaults, **overrides})


def fully_loaded_lead() -> GeneratedLead:
    """Every positive signal except provider phone verification, which is Phase 2."""
    lead = make_lead(
        phone_e164="+201001234567",
        website="https://karam.com.eg",
        website_domain="karam.com.eg",
        rating="4.8",
        reviews_count=900,
        branch_count=6,
    )
    WebsiteProfile.objects.create(
        lead=lead,
        emails=["info@karam.com.eg"],
        delivery_platforms=["talabat"],
    )
    for platform in (enums.SocialPlatform.INSTAGRAM, enums.SocialPlatform.FACEBOOK):
        SocialProfile.objects.create(
            lead=lead, platform=platform, url=f"https://{platform}.com/karam"
        )
    return lead


def points_for(breakdown: list[dict], key: str) -> int:
    return next(row["points"] for row in breakdown if row["key"] == key)


class TestClosedBusiness:
    def test_permanently_closed_scores_zero_regardless_of_other_signals(self):
        """A closed business is not a weak prospect, it is not a prospect. Its
        website and 900 reviews must not float it to the top of the queue."""
        lead = fully_loaded_lead()
        lead.business_status = "CLOSED_PERMANENTLY"
        score, label, breakdown = scoring.score_lead(lead)

        assert score == 0
        assert label == enums.ScoreLabel.IGNORE
        assert breakdown[0]["key"] == "closed"


class TestWeightBudget:
    def test_positive_weights_sum_to_exactly_one_hundred(self):
        """Mirrors console.crm's precedent: a full bar means every signal fired,
        so the total never needs clamping to stay in range."""
        total = (
            scoring.WEBSITE_POINTS
            + scoring.EMAIL_POINTS
            + scoring.INSTAGRAM_POINTS
            + scoring.FACEBOOK_POINTS
            + scoring.PHONE_VALID_POINTS
            + scoring.PHONE_VERIFIED_POINTS
            + scoring.DIGITAL_PRESENCE_POINTS
            + scoring.REVIEW_TIERS[0][1]
            + scoring.RATING_TIERS[0][1]
            + scoring.BRANCH_TIERS[0][1]
        )
        assert total == scoring.SCORE_MAX

    def test_best_unverified_lead_is_warm_not_hot(self):
        """The reason the spec's 20-point phone weight was split. Hot means
        verified; without the verification stage nothing may claim it."""
        score, label, _ = scoring.score_lead(fully_loaded_lead())

        assert score == scoring.SCORE_MAX - scoring.PHONE_VERIFIED_POINTS
        assert label == enums.ScoreLabel.WARM
        assert score < scoring.HOT_MIN

    def test_bare_listing_is_ignored(self):
        score, label, _ = scoring.score_lead(make_lead())
        assert score == 0
        assert label == enums.ScoreLabel.IGNORE


class TestSignals:
    def test_valid_phone_scores_and_unparseable_does_not(self):
        assert points_for(
            scoring.score_lead(make_lead(phone_e164="+201001234567"))[2], "phone_valid"
        ) == scoring.PHONE_VALID_POINTS
        assert points_for(scoring.score_lead(make_lead(phone="0100 bad"))[2], "phone_valid") == 0

    def test_website_scores_on_domain_not_raw_url(self):
        lead = make_lead(website="https://karam.com.eg", website_domain="karam.com.eg")
        assert points_for(scoring.score_lead(lead)[2], "website") == scoring.WEBSITE_POINTS

    def test_email_requires_a_crawled_profile(self):
        lead = make_lead()
        assert points_for(scoring.score_lead(lead)[2], "email") == 0
        WebsiteProfile.objects.create(lead=lead, emails=["info@karam.com.eg"])
        lead.refresh_from_db()
        assert points_for(scoring.score_lead(lead)[2], "email") == scoring.EMAIL_POINTS

    @pytest.mark.parametrize(
        ("reviews", "expected"),
        [(0, 0), (49, 0), (50, 5), (199, 5), (200, 10), (499, 10), (500, 15), (5000, 15)],
    )
    def test_review_tiers_are_graduated(self, reviews, expected):
        """Graduated rather than the spec's single 500-review cliff: a cafe with
        300 reviews is plainly a better prospect than one with 4."""
        lead = make_lead(reviews_count=reviews)
        assert points_for(scoring.score_lead(lead)[2], "reviews") == expected

    @pytest.mark.parametrize(
        ("rating", "expected"), [(None, 0), ("3.9", 0), ("4.0", 5), ("4.5", 10), ("5.0", 10)]
    )
    def test_rating_tiers(self, rating, expected):
        lead = make_lead(rating=rating)
        assert points_for(scoring.score_lead(lead)[2], "rating") == expected

    @pytest.mark.parametrize(
        ("branches", "expected"), [(1, 0), (2, 10), (3, 10), (4, 20), (40, 20)]
    )
    def test_branch_tiers(self, branches, expected):
        """Branch count comes from dedupe collapsing a chain's listings."""
        lead = make_lead(branch_count=branches)
        assert points_for(scoring.score_lead(lead)[2], "branches") == expected

    def test_social_platforms_score_independently(self):
        lead = make_lead()
        SocialProfile.objects.create(
            lead=lead, platform=enums.SocialPlatform.INSTAGRAM, url="https://ig.com/karam"
        )
        breakdown = scoring.score_lead(lead)[2]
        assert points_for(breakdown, "instagram") == scoring.INSTAGRAM_POINTS
        assert points_for(breakdown, "facebook") == 0


class TestNegativeSignals:
    def test_existing_loyalty_vendor_deducts(self):
        lead = fully_loaded_lead()
        before = scoring.score_lead(lead)[0]

        profile = lead.website_profile
        profile.loyalty_vendors = ["smiles"]
        profile.save(update_fields=["loyalty_vendors"])
        lead.refresh_from_db()

        after, _, breakdown = scoring.score_lead(lead)
        assert after == before + scoring.ALREADY_LOYALTY_PENALTY
        assert points_for(breakdown, "existing_loyalty") == scoring.ALREADY_LOYALTY_PENALTY

    def test_score_never_goes_negative(self):
        """The spam penalty is -50 and could otherwise drive a bare lead below
        zero, which the UI has no way to render."""
        lead = make_lead()
        WebsiteProfile.objects.create(lead=lead, loyalty_vendors=["smiles"])
        lead.refresh_from_db()
        assert scoring.score_lead(lead)[0] == 0


class TestBreakdown:
    def test_absent_signals_still_appear_with_zero(self):
        """A rep disputing a score must see what was checked, not only what
        fired — an itemised zero is the difference between "we looked and found
        nothing" and "we never looked"."""
        breakdown = scoring.score_lead(make_lead())[2]
        keys = {row["key"] for row in breakdown}
        assert {"phone_valid", "website", "email", "instagram", "facebook", "reviews"} <= keys
        assert all(row["points"] == 0 for row in breakdown)

    def test_every_row_carries_a_human_label_and_detail(self):
        for row in scoring.score_lead(fully_loaded_lead())[2]:
            assert row["label"]
            assert row["detail"]


class TestLabels:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, enums.ScoreLabel.HOT),
            (90, enums.ScoreLabel.HOT),
            (89, enums.ScoreLabel.WARM),
            (70, enums.ScoreLabel.WARM),
            (69, enums.ScoreLabel.COLD),
            (50, enums.ScoreLabel.COLD),
            (49, enums.ScoreLabel.IGNORE),
            (0, enums.ScoreLabel.IGNORE),
        ],
    )
    def test_thresholds(self, score, expected):
        assert scoring.label_for(score) == expected
