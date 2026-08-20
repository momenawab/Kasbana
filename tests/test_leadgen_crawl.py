"""Tests for website-crawl extraction.

Parsing only — no network. Each test feeds the extractors the kind of markup a
small-business site actually serves, including the Arabic and the messy cases.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from leadgen import crawl


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestEmailExtraction:
    def test_reads_mailto_and_body_text(self):
        html = """
          <a href="mailto:Ahmed@Karam.com.eg">write us</a>
          <p>or reach us at hello@karam.com.eg</p>
        """
        assert crawl._extract_emails(soup_of(html), html) == [
            "ahmed@karam.com.eg",
            "hello@karam.com.eg",
        ]

    @pytest.mark.parametrize(
        "address",
        ["noreply@karam.com.eg", "no-reply@karam.com.eg", "postmaster@karam.com.eg"],
    )
    def test_drops_unreachable_boxes(self, address):
        html = f'<a href="mailto:{address}">mail</a>'
        assert crawl._extract_emails(soup_of(html), html) == []

    def test_does_not_mistake_retina_image_names_for_emails(self):
        """ "logo@2x.png" matches the email shape and appears on a lot of sites."""
        html = '<img src="/img/logo@2x.png">'
        assert crawl._extract_emails(soup_of(html), html) == []

    def test_role_addresses_are_kept(self):
        """For a small cafe, info@ is very often the owner — keep it as a
        contact; owner resolution is what treats it as a department."""
        html = '<a href="mailto:info@karam.com.eg">contact</a>'
        assert crawl._extract_emails(soup_of(html), html) == ["info@karam.com.eg"]


class TestLegalEntity:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("© 2026 Karam Group for Restaurants", "Karam Group for Restaurants"),
            ("© 2019-2026 Karam Group", "Karam Group"),
            (
                "This site is operated by Karam Group for Restaurants.",
                "Karam Group for Restaurants",
            ),
            ("All rights reserved to Karam Group", "Karam Group"),
        ],
    )
    def test_extracts_operating_entity(self, text, expected):
        assert crawl._legal_entity(text) == expected

    def test_arabic_copyright(self):
        assert crawl._legal_entity("جميع الحقوق محفوظة لشركة كرم") != ""

    def test_no_entity_returns_empty(self):
        assert crawl._legal_entity("We have served Maadi since 2011.") == ""

    def test_run_on_navigation_text_is_rejected(self):
        """Observed live on zazacuisine.com: stripped page copy often has no
        sentence punctuation, so the © capture ran 80 chars into the nav bar.
        This value reaches the CRM's company field, so noise is worse than "".
        """
        text = (
            "© 2024 Privacy Policy Developed By Shoman Systems"
            " Item was added successfully Continu"
        )
        assert crawl._legal_entity(text) == ""

    @pytest.mark.parametrize(
        "text",
        [
            "© 2026 Developed by Shoman Systems",
            "© 2026 Designed by Some Agency",
            "© 2026 Powered by Shopify",
        ],
    )
    def test_web_agency_is_not_the_business(self, text):
        """The agency that built the site is not the company we are selling to."""
        assert crawl._legal_entity(text) == ""

    def test_finds_a_valid_entity_after_skipping_a_noisy_match(self):
        text = "© Privacy Policy and Terms · All rights reserved to Karam Group"
        assert crawl._legal_entity(text) == "Karam Group"


class TestMetaAndLogo:
    def test_meta_description_prefers_name_over_og(self):
        html = """
          <meta name="description" content="Specialty coffee in Maadi">
          <meta property="og:description" content="og fallback">
        """
        assert crawl._meta_description(soup_of(html)) == "Specialty coffee in Maadi"

    def test_falls_back_to_og_description(self):
        html = '<meta property="og:description" content="og fallback">'
        assert crawl._meta_description(soup_of(html)) == "og fallback"

    def test_logo_prefers_og_image(self):
        html = '<meta property="og:image" content="/img/share.png">'
        assert crawl._logo_url(soup_of(html), "https://karam.com.eg") == (
            "https://karam.com.eg/img/share.png"
        )

    def test_logo_falls_back_to_marked_up_image(self):
        html = '<img class="site-logo" src="/img/brand.svg">'
        assert crawl._logo_url(soup_of(html), "https://karam.com.eg") == (
            "https://karam.com.eg/img/brand.svg"
        )

    def test_no_logo_returns_empty(self):
        assert crawl._logo_url(soup_of("<img src='/hero.jpg'>"), "https://karam.com.eg") == ""


class TestPageKind:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("/privacy-policy", "legal"),
            ("/terms", "legal"),
            ("/about-us", "about"),
            ("/our-story", "about"),
            ("/contact", "contact"),
            ("/", "home"),
        ],
    )
    def test_classification(self, path, expected):
        assert crawl._page_kind(path) == expected


class TestVendorSignatures:
    def test_detects_regional_pos_and_loyalty(self):
        """Foodics and Marn are what Egyptian F&B actually runs — a global-only
        signature list would report "no POS" on most real sites."""
        assert "foodics" in crawl.POS_SIGNATURES
        assert "marn" in crawl.POS_SIGNATURES

    def test_signature_lists_do_not_overlap_across_categories(self):
        """A vendor claimed by two categories would double-count in scoring."""
        seen: dict[str, str] = {}
        for category, signatures in (
            ("pos", crawl.POS_SIGNATURES),
            ("loyalty", crawl.LOYALTY_SIGNATURES),
            ("payment", crawl.PAYMENT_SIGNATURES),
            ("delivery", crawl.DELIVERY_SIGNATURES),
            ("reservation", crawl.RESERVATION_SIGNATURES),
        ):
            for vendor in signatures:
                assert vendor not in seen, f"{vendor} in both {seen.get(vendor)} and {category}"
                seen[vendor] = category


class TestCrawlGuards:
    """``crawl()`` must refuse before it opens a connection."""

    def test_platform_domain_is_never_fetched(self):
        """A Places "website" is often an Instagram profile. Following it is
        forbidden, futile, and would put our IP in front of a bot wall."""
        result = crawl.WebsiteCrawler().crawl("https://www.instagram.com/1980.coffee")
        assert not result.succeeded
        assert "platform" in result.error
        assert result.pages_crawled == 0

    def test_chain_parent_domain_is_never_fetched(self):
        result = crawl.WebsiteCrawler().crawl("https://www.ihg.com/holidayinn/hotels/eg")
        assert not result.succeeded
        assert result.pages_crawled == 0

    def test_unusable_url_fails_cleanly(self):
        result = crawl.WebsiteCrawler().crawl("not a url")
        assert not result.succeeded
        assert result.error

    def test_empty_url_fails_cleanly(self):
        assert not crawl.WebsiteCrawler().crawl("").succeeded


class TestDedupeLists:
    def test_repeats_across_pages_collapse_preserving_order(self):
        result = crawl.CrawlResult(url="https://karam.com.eg")
        result.emails = ["b@x.com", "a@x.com", "b@x.com"]
        result.technologies = ["wordpress", "wordpress"]
        crawl._dedupe_lists(result)
        assert result.emails == ["b@x.com", "a@x.com"]
        assert result.technologies == ["wordpress"]
