"""Tests for owner-name resolution and the page-extraction helpers it reads.

The behaviour under protection is restraint: the module must find a name when
one is published and return nothing when one is not. A confident wrong name is
worse than an empty field, because a rep opens the call with it.
"""

from __future__ import annotations

import pytest

from leadgen import crawl, enums, owner


def result_with(*sources: tuple[str, str, str]) -> crawl.CrawlResult:
    res = crawl.CrawlResult(url="https://karam.com.eg")
    res.owner_sources = list(sources)
    return res


class TestNameShapeGuard:
    @pytest.mark.parametrize("value", ["Ahmed Karam", "Mona El Sayed", "Karim Abdel Aziz"])
    def test_accepts_real_names(self, value):
        assert owner._looks_like_a_name(value) is True

    @pytest.mark.parametrize(
        "value",
        ["Our Story", "Privacy Policy", "All Rights", "Read More", "Karam", "Ahmed 2024"],
    )
    def test_rejects_page_furniture_and_single_words(self, value):
        """Without this guard, "Our Story" becomes a candidate owner on
        practically every site that has an about page."""
        assert owner._looks_like_a_name(value) is False


class TestExtractFromPages:
    def test_name_then_role(self):
        res = result_with(("https://karam.com.eg/about", "about", "Ahmed Karam, Founder"))
        found = owner.extract_from_pages(res)
        assert found[0]["name"] == "Ahmed Karam"
        assert found[0]["source"] == enums.OwnerNameSource.ABOUT_PAGE

    def test_role_then_name(self):
        res = result_with(("https://karam.com.eg/about", "about", "Owner: Mona El Sayed"))
        assert owner.extract_from_pages(res)[0]["name"] == "Mona El Sayed"

    def test_arabic_role_then_name(self):
        res = result_with(("https://karam.com.eg/about", "about", "المالك: احمد كرم"))
        found = owner.extract_from_pages(res)
        assert found
        assert "احمد" in found[0]["name"]

    def test_legal_page_outranks_footer(self):
        res = result_with(
            ("https://karam.com.eg/", "footer", "Managed by Sara Nabil"),
            ("https://karam.com.eg/privacy", "legal", "Owner: Ahmed Karam"),
        )
        winner = owner.resolve(owner.extract_from_pages(res))
        assert winner["name"] == "Ahmed Karam"
        assert winner["confidence"] == enums.Confidence.HIGH

    def test_decisive_role_outranks_vague_one_on_the_same_page(self):
        res = result_with(
            (
                "https://karam.com.eg/team",
                "about",
                "Sara Nabil, Branch Manager. Ahmed Karam, Founder.",
            )
        )
        assert owner.resolve(owner.extract_from_pages(res))["name"] == "Ahmed Karam"

    def test_every_candidate_carries_checkable_evidence(self):
        res = result_with(("https://karam.com.eg/about", "about", "Ahmed Karam, Founder"))
        candidate = owner.extract_from_pages(res)[0]
        assert candidate["evidence_url"] == "https://karam.com.eg/about"
        assert "Ahmed Karam" in candidate["evidence_text"]

    def test_page_with_no_named_owner_yields_nothing(self):
        res = result_with(
            ("https://karam.com.eg/about", "about", "We serve the best coffee in Maadi since 2011.")
        )
        assert owner.extract_from_pages(res) == []


class TestExtractFromEmails:
    def test_personal_looking_address(self):
        found = owner.extract_from_emails(["ahmed.karam@karam.com.eg"])
        assert found[0]["name"] == "Ahmed Karam"
        assert found[0]["confidence"] == enums.Confidence.LOW

    @pytest.mark.parametrize(
        "email", ["info@karam.com.eg", "bookings@karam.com.eg", "hello@karam.com.eg"]
    )
    def test_role_addresses_are_not_people(self, email):
        assert owner.extract_from_emails([email]) == []

    def test_single_token_local_part_is_not_offered(self):
        """ "ahmed@" could be a person, but equally a brand or a department —
        not enough to put a name in front of a rep."""
        assert owner.extract_from_emails(["ahmed@karam.com.eg"]) == []


class TestResolve:
    def test_returns_none_when_nothing_fired(self):
        """The common outcome for small Egyptian cafes, and it must survive as
        an empty field rather than a guess."""
        assert owner.resolve([]) is None

    def test_email_never_beats_a_published_page(self):
        candidates = owner.extract_from_pages(
            result_with(("https://karam.com.eg/privacy", "legal", "Owner: Ahmed Karam"))
        ) + owner.extract_from_emails(["mona.sayed@karam.com.eg"])
        assert owner.resolve(candidates)["name"] == "Ahmed Karam"


class TestDeduplicate:
    def test_same_person_on_two_pages_collapses_to_best_source(self):
        candidates = owner.extract_from_pages(
            result_with(
                ("https://karam.com.eg/", "footer", "Ahmed Karam, Owner"),
                ("https://karam.com.eg/privacy", "legal", "Ahmed Karam, Owner"),
            )
        )
        collapsed = owner.deduplicate(candidates)
        assert len(collapsed) == 1
        assert collapsed[0]["source"] == enums.OwnerNameSource.LEGAL_PAGE

    def test_different_people_are_both_kept(self):
        candidates = owner.extract_from_pages(
            result_with(
                (
                    "https://karam.com.eg/team",
                    "about",
                    "Ahmed Karam, Founder. Mona Sayed, Director.",
                )
            )
        )
        assert len({c["name"] for c in owner.deduplicate(candidates)}) == 2


class TestCompanyIsNotAPerson:
    def test_legal_entity_is_returned_separately(self):
        """A company must never be offered as the owner's name — "Dear Karam
        Group for Restaurants" is worse than no greeting at all."""
        res = crawl.CrawlResult(url="https://karam.com.eg")
        res.legal_entity = "Karam Group for Restaurants"
        assert owner.company_name(res) == "Karam Group for Restaurants"
        assert owner.resolve(owner.extract_from_pages(res)) is None
