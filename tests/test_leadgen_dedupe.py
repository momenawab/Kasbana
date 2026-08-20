"""Tests for lead-generation canonicalisation and duplicate detection.

Pure functions, so no database. The cases that matter are the Egyptian ones:
Arabic spelling variance and the ``.com.eg`` public suffix are where a naive
implementation silently merges or splits the entire result set.
"""

from __future__ import annotations

import pytest

from leadgen import dedupe


class TestNormalizeName:
    def test_folds_case_punctuation_and_latin_accents(self):
        assert dedupe.normalize_name("Café Karam!") == dedupe.normalize_name("CAFE KARAM")

    def test_word_order_does_not_matter(self):
        assert dedupe.normalize_name("Cafe Karam") == dedupe.normalize_name("Karam Cafe")

    def test_filler_words_are_dropped(self):
        assert dedupe.normalize_name("The Karam Company") == "karam"

    def test_business_type_words_are_kept(self):
        """ "Kitchen" and "grill" look generic but distinguish real businesses —
        stripping them would merge "Cairo Kitchen" into "Cairo Grill"."""
        assert "kitchen" in dedupe.normalize_name("Cairo Kitchen")
        assert dedupe.normalize_name("Cairo Kitchen") != dedupe.normalize_name("Cairo Grill")

    def test_branch_suffix_is_dropped(self):
        """A chain's branches collapse onto one lead: one head office, one sale."""
        assert dedupe.normalize_name("Karam Cafe Maadi") == dedupe.normalize_name(
            "Karam Cafe Zamalek"
        )

    def test_city_names_are_kept_as_brand(self):
        """Neighbourhoods are branch qualifiers; cities are often the brand."""
        assert "cairo" in dedupe.normalize_name("Cairo Kitchen")

    @pytest.mark.parametrize(
        "variant",
        [
            "مطعم كرم",  # plain alef
            "مطعم كرم ",  # trailing space
            "مَطعم كرم",  # with a diacritic
            "مطــعم كرم",  # with tatweel
        ],
    )
    def test_arabic_variants_normalise_together(self, variant):
        """Hand-typed Arabic listings vary by diacritic, tatweel and alef form.
        All of these are one business to a reader and must be one to us."""
        assert dedupe.normalize_name(variant) == dedupe.normalize_name("مطعم كرم")

    def test_alef_hamza_forms_fold(self):
        assert dedupe.normalize_name("أحمد") == dedupe.normalize_name("احمد")

    def test_ta_marbuta_and_alef_maqsura_fold(self):
        assert dedupe.normalize_name("قهوة") == dedupe.normalize_name("قهوه")

    def test_arabic_indic_digits_fold_to_ascii(self):
        assert dedupe.normalize_name("كرم ٢") == dedupe.normalize_name("كرم 2")

    def test_all_filler_name_returns_empty(self):
        """An all-filler name is unmatchable, not universally matching. The
        dedupe stage must not treat two empty results as the same business."""
        assert dedupe.normalize_name("The Company") == ""

    def test_empty_input(self):
        assert dedupe.normalize_name("") == ""


class TestNameSimilarity:
    def test_identical_normalised_names(self):
        assert dedupe.name_similarity("karam", "karam") == 1.0

    def test_empty_never_matches(self):
        """Guards the all-generic case above: "" must not match anything."""
        assert dedupe.name_similarity("", "") == 0.0
        assert dedupe.name_similarity("", "karam") == 0.0

    def test_branches_of_one_chain_exceed_threshold(self):
        left = dedupe.normalize_name("Karam Cafe Maadi")
        right = dedupe.normalize_name("Karam Cafe Zamalek")
        assert dedupe.name_similarity(left, right) >= dedupe.NAME_MATCH_THRESHOLD

    def test_different_neighbours_stay_below_threshold(self):
        left = dedupe.normalize_name("Beanos")
        right = dedupe.normalize_name("Bean Bar")
        assert dedupe.name_similarity(left, right) < dedupe.NAME_MATCH_THRESHOLD

    def test_shared_first_word_does_not_merge_distinct_businesses(self):
        """The false merge this design most needs to avoid."""
        left = dedupe.normalize_name("Cairo Kitchen")
        right = dedupe.normalize_name("Cairo Grill")
        assert dedupe.name_similarity(left, right) < dedupe.NAME_MATCH_THRESHOLD

    def test_transliteration_wobble_still_matches(self):
        left = dedupe.normalize_name("Karam Cafe")
        right = dedupe.normalize_name("Karm Cafe")
        assert dedupe.name_similarity(left, right) >= dedupe.NAME_MATCH_THRESHOLD

    def test_extra_distinguishing_word_lowers_similarity(self):
        """ "Karam" is not "Karam Express" — a subset must not score as a match."""
        left = dedupe.normalize_name("Karam")
        right = dedupe.normalize_name("Karam Express Delivery")
        assert dedupe.name_similarity(left, right) < dedupe.NAME_MATCH_THRESHOLD


class TestNormalizePhone:
    def test_local_egyptian_mobile_becomes_e164(self):
        assert dedupe.normalize_phone("0100 123 4567", "EG") == "+201001234567"

    def test_already_international(self):
        assert dedupe.normalize_phone("+20 100 123 4567", "EG") == "+201001234567"

    def test_formatting_variants_converge(self):
        """The dedupe key only works if these three listings agree."""
        forms = ["+201001234567", "0100-123-4567", "(0100) 123 4567"]
        assert len({dedupe.normalize_phone(f, "EG") for f in forms}) == 1

    def test_arabic_indic_digits(self):
        assert dedupe.normalize_phone("٠١٠٠١٢٣٤٥٦٧", "EG") == "+201001234567"

    def test_invalid_returns_empty_rather_than_raising(self):
        """A malformed phone is ordinary on a Places listing and must not fail
        the lead — the raw value stays readable on the record."""
        assert dedupe.normalize_phone("not a phone", "EG") == ""
        assert dedupe.normalize_phone("123", "EG") == ""

    def test_empty_input(self):
        assert dedupe.normalize_phone("", "EG") == ""


class TestRegistrableDomain:
    def test_strips_scheme_www_path_and_case(self):
        assert dedupe.registrable_domain("https://www.Karam.com/menu") == "karam.com"

    def test_egyptian_second_level_suffix(self):
        """The reason tldextract is a dependency: a two-label split would
        return "com.eg" here and collapse every Egyptian lead into one."""
        assert dedupe.registrable_domain("https://www.karam.com.eg/") == "karam.com.eg"

    def test_two_egyptian_domains_stay_distinct(self):
        assert dedupe.registrable_domain("http://karam.com.eg") != dedupe.registrable_domain(
            "http://beanos.com.eg"
        )

    def test_subdomain_folds_to_registrable(self):
        assert dedupe.registrable_domain("https://order.karam.com.eg") == "karam.com.eg"

    def test_garbage_returns_empty(self):
        assert dedupe.registrable_domain("not a url") == ""
        assert dedupe.registrable_domain("") == ""


class TestOwnDomain:
    """Guards two failures seen on the first live Maadi search: one cafe's
    Places "website" was an Instagram profile, another's was ihg.com."""

    def test_real_business_domain_is_own(self):
        assert dedupe.is_own_domain("karam.com.eg") is True

    @pytest.mark.parametrize(
        "domain",
        ["instagram.com", "facebook.com", "linktr.ee", "talabat.com", "ihg.com", "booking.com"],
    )
    def test_platform_domains_are_not_own(self, domain):
        assert dedupe.is_own_domain(domain) is False

    def test_empty_is_not_own(self):
        assert dedupe.is_own_domain("") is False

    def test_platform_domain_must_not_become_a_dedupe_key(self):
        """Two unrelated cafes both listing an Instagram URL are not one business."""
        left = dedupe.registrable_domain("https://instagram.com/cafe.one")
        right = dedupe.registrable_domain("https://instagram.com/cafe.two")
        assert left == right  # same registrable domain …
        assert not dedupe.is_own_domain(left)  # … so it may not key the dedupe


class TestSocialPlatformFor:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://www.instagram.com/1980.coffee", "instagram"),
            ("https://facebook.com/karamcafe", "facebook"),
            ("https://wa.me/201001234567", "whatsapp"),
            ("https://www.tiktok.com/@karam", "tiktok"),
        ],
    )
    def test_recognises_social_urls(self, url, expected):
        assert dedupe.social_platform_for(url) == expected

    def test_business_site_is_not_social(self):
        assert dedupe.social_platform_for("https://karam.com.eg") == ""


class TestHaversine:
    def test_zero_distance(self):
        assert dedupe.haversine_meters(30.0444, 31.2357, 30.0444, 31.2357) == 0.0

    def test_same_storefront_is_within_threshold(self):
        """Two Places pins on one building differ by a few tens of metres."""
        d = dedupe.haversine_meters(30.04440, 31.23570, 30.04470, 31.23590)
        assert d < dedupe.SAME_LOCATION_METERS

    def test_across_cairo_is_far_outside_threshold(self):
        maadi_to_zamalek = dedupe.haversine_meters(29.9602, 31.2569, 30.0614, 31.2197)
        assert maadi_to_zamalek > 10_000
