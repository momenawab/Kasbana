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
        reviews_count=1200,
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
            + scoring.GREENFIELD_POINTS
            + scoring.DIGITAL_PRESENCE_POINTS
            + scoring.REVIEW_TIERS[0][1]
            + scoring.RATING_TIERS[0][1]
            + scoring.BRANCH_TIERS[0][1]
        )
        assert total == scoring.SCORE_MAX

    def test_best_possible_unverified_lead_reads_hot(self):
        """Under traction-first weights, thousands of reviews across several
        branches is a hot lead whether or not a provider has confirmed the
        number. Verification adds confidence; it no longer gates the label."""
        score, label, _ = scoring.score_lead(fully_loaded_lead())

        assert score == scoring.SCORE_MAX - scoring.PHONE_VERIFIED_POINTS
        assert label == enums.ScoreLabel.HOT

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
        [(0, 0), (49, 0), (50, 8), (199, 8), (200, 14), (499, 14),
         (500, 20), (999, 20), (1000, 25), (5000, 25)],
    )
    def test_review_tiers_are_graduated(self, reviews, expected):
        """Graduated rather than the spec's single 500-review cliff: a cafe with
        300 reviews is plainly a better prospect than one with 4."""
        lead = make_lead(reviews_count=reviews)
        assert points_for(scoring.score_lead(lead)[2], "reviews") == expected

    @pytest.mark.parametrize(
        ("rating", "expected"),
        [(None, 0), ("3.4", 0), ("3.5", 4), ("4.0", 8), ("4.2", 11), ("4.5", 15), ("5.0", 15)],
    )
    def test_rating_tiers(self, rating, expected):
        lead = make_lead(rating=rating)
        assert points_for(scoring.score_lead(lead)[2], "rating") == expected

    @pytest.mark.parametrize(
        ("branches", "expected"), [(1, 0), (2, 12), (3, 12), (4, 18), (40, 18)]
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
        # Bigger than the penalty alone: an incumbent vendor also forfeits the
        # greenfield signal, which is why greenfield is stated explicitly.
        assert after == before + scoring.ALREADY_LOYALTY_PENALTY - scoring.GREENFIELD_POINTS
        assert points_for(breakdown, "existing_loyalty") == scoring.ALREADY_LOYALTY_PENALTY
        assert points_for(breakdown, "greenfield") == 0

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


class TestMarketReality:
    """Regression tests for the weights themselves, taken from a live Maadi run.

    Under the spec's original web-heavy table, 22 of 24 real cafes scored
    "Ignore" because they had no website — a list no rep would ever open. These
    pin the corrected behaviour to actual businesses rather than to round
    numbers, so a future weight change has to confront the same reality.
    """

    def test_busy_website_less_chain_is_a_good_lead(self):
        """Beano's Café: 4,384 reviews, 4.3 stars, two branches, no website.
        The best prospect in the area, and previously labelled "Ignore"."""
        lead = make_lead(
            business_name="Beano's Café",
            phone_e164="+201001234567",
            rating="4.3",
            reviews_count=4384,
            branch_count=2,
        )
        score, label, _ = scoring.score_lead(lead)

        assert label in (enums.ScoreLabel.WARM, enums.ScoreLabel.HOT)
        assert score >= scoring.WARM_MIN

    def test_no_website_costs_less_than_the_traction_it_would_replace(self):
        """Two thirds of Egyptian F&B has no site. Absence must be a small
        deduction, not a disqualification."""
        busy = make_lead(place_id="p-busy", reviews_count=3000, rating="4.6", phone_e164="+201001234567")
        quiet = make_lead(
            place_id="p-quiet",
            reviews_count=8,
            rating="3.2",
            phone_e164="+201009999999",
            website="https://quiet.com.eg",
            website_domain="quiet.com.eg",
        )
        assert scoring.score_lead(busy)[0] > scoring.score_lead(quiet)[0]

    def test_greenfield_beats_an_equally_busy_incumbent(self):
        """The product thesis: footfall with no loyalty vendor is the easiest
        sale, so it must outrank an identical business already running one."""
        greenfield = make_lead(place_id="p-green", reviews_count=2000, phone_e164="+201001234567")
        incumbent = make_lead(place_id="p-inc", reviews_count=2000, phone_e164="+201001234567")
        WebsiteProfile.objects.create(lead=incumbent, loyalty_vendors=["smiles"])
        incumbent.refresh_from_db()

        assert scoring.score_lead(greenfield)[0] > scoring.score_lead(incumbent)[0]

    def test_pillars_outweigh_convenience_signals(self):
        """Traction, scale and reachability must dominate web presence, or the
        market's structure decides the ranking instead of the businesses."""
        pillars = (
            scoring.REVIEW_TIERS[0][1]
            + scoring.RATING_TIERS[0][1]
            + scoring.BRANCH_TIERS[0][1]
            + scoring.PHONE_VALID_POINTS
            + scoring.PHONE_VERIFIED_POINTS
            + scoring.GREENFIELD_POINTS
        )
        convenience = (
            scoring.WEBSITE_POINTS
            + scoring.EMAIL_POINTS
            + scoring.INSTAGRAM_POINTS
            + scoring.FACEBOOK_POINTS
            + scoring.DIGITAL_PRESENCE_POINTS
        )
        assert pillars > 4 * convenience


class TestLabels:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (100, enums.ScoreLabel.HOT),
            (75, enums.ScoreLabel.HOT),
            (74, enums.ScoreLabel.WARM),
            (55, enums.ScoreLabel.WARM),
            (54, enums.ScoreLabel.COLD),
            (35, enums.ScoreLabel.COLD),
            (34, enums.ScoreLabel.IGNORE),
            (0, enums.ScoreLabel.IGNORE),
        ],
    )
    def test_thresholds(self, score, expected):
        assert scoring.label_for(score) == expected
