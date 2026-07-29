"""Tests for phone and email verification.

Two properties matter more than provider plumbing:

* the pipeline still works with no provider configured, and
* the weaker offline answer is *labelled* weaker, so a rep can tell how much to
  trust it. A fallback that claimed VERIFIED would be worse than no fallback.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from leadgen import enums, verify
from leadgen.models import ApiUsage, GeneratedLead, SearchJob, Verification, WebsiteProfile
from leadgen.services import verification

pytestmark = pytest.mark.django_db


def make_lead(**overrides) -> GeneratedLead:
    job = SearchJob.objects.create(country="EG", city="Cairo", business_types=["cafe"])
    defaults = {"place_id": "p1", "business_name": "Karam Cafe", "business_status": "OPERATIONAL"}
    return GeneratedLead.objects.create(job=job, **{**defaults, **overrides})


@pytest.fixture(autouse=True)
def no_providers(settings):
    """Default to the offline path; provider tests opt in explicitly."""
    settings.TWILIO_ACCOUNT_SID = ""
    settings.TWILIO_AUTH_TOKEN = ""
    settings.HUNTER_API_KEY = ""


class TestPhoneOffline:
    def test_valid_egyptian_mobile_is_possible_not_verified(self):
        """libphonenumber proves the number could exist, not that anyone
        answers. Claiming VERIFIED would put unearned confidence on screen."""
        outcome = verify.verify_phone("+201001234567", region="EG")

        assert outcome.result == enums.VerificationResult.POSSIBLE
        assert outcome.line_type == enums.PhoneLineType.MOBILE
        assert outcome.provider == ""
        assert outcome.cost_usd == 0

    def test_invalid_number_is_invalid_offline(self):
        outcome = verify.verify_phone("+2010012", region="EG")
        assert outcome.result == enums.VerificationResult.INVALID

    def test_empty_number(self):
        assert verify.verify_phone("", region="EG").result == enums.VerificationResult.INVALID

    def test_offline_never_claims_verified(self):
        for number in ("+201001234567", "+20223585336"):
            assert verify.verify_phone(number, region="EG").result != (
                enums.VerificationResult.VERIFIED
            )


class TestPhoneWithTwilio:
    @pytest.fixture(autouse=True)
    def creds(self, settings):
        settings.TWILIO_ACCOUNT_SID = "AC123"
        settings.TWILIO_AUTH_TOKEN = "secret"

    def _response(self, status=200, body=None):
        class R:
            status_code = status

            def json(self):
                return body or {}

        return R()

    def test_verified_mobile(self):
        body = {
            "valid": True,
            "line_type_intelligence": {"type": "mobile", "carrier_name": "Vodafone"},
        }
        with patch("httpx.Client.get", return_value=self._response(200, body)):
            outcome = verify.verify_phone("+201001234567", region="EG")

        assert outcome.result == enums.VerificationResult.VERIFIED
        assert outcome.line_type == enums.PhoneLineType.MOBILE
        assert outcome.carrier_name == "Vodafone"
        assert outcome.credits_used == 1

    def test_unknown_number_is_invalid(self):
        with patch("httpx.Client.get", return_value=self._response(404)):
            outcome = verify.verify_phone("+201001234567", region="EG")
        assert outcome.result == enums.VerificationResult.INVALID

    def test_provider_outage_degrades_to_offline_rather_than_failing(self):
        import httpx

        with patch("httpx.Client.get", side_effect=httpx.ConnectError("down")):
            outcome = verify.verify_phone("+201001234567", region="EG")

        assert outcome.result == enums.VerificationResult.POSSIBLE
        assert "offline analysis" in outcome.error

    def test_unparseable_number_never_spends_a_credit(self):
        with patch("httpx.Client.get") as called:
            verify.verify_phone("nonsense", region="EG")
        assert not called.called


class TestEmailOffline:
    def test_live_domain_is_possible(self):
        with patch("leadgen.verify._domain_resolves", return_value=True):
            outcome = verify.verify_email("hello@karam.com.eg")
        assert outcome.result == enums.VerificationResult.POSSIBLE
        assert outcome.domain_valid is True

    def test_dead_domain_is_invalid(self):
        with patch("leadgen.verify._domain_resolves", return_value=False):
            outcome = verify.verify_email("hello@nope.invalid")
        assert outcome.result == enums.VerificationResult.INVALID

    def test_disposable_address_is_rejected(self):
        outcome = verify.verify_email("someone@mailinator.com")
        assert outcome.result == enums.VerificationResult.INVALID
        assert outcome.is_disposable is True

    def test_role_address_is_flagged_but_kept(self):
        """For a small cafe info@ is often the owner — useful, but a rep should
        know before writing "Dear info"."""
        with patch("leadgen.verify._domain_resolves", return_value=True):
            outcome = verify.verify_email("info@karam.com.eg")
        assert outcome.is_role_address is True
        assert outcome.result == enums.VerificationResult.POSSIBLE

    def test_malformed_address(self):
        assert verify.verify_email("not-an-email").result == enums.VerificationResult.INVALID

    def test_offline_never_probes_a_mailbox(self):
        """SMTP probing gets a server IP blocklisted — a permanent, platform-wide
        cost for a marginal signal on one lead."""
        import socket

        with patch.object(socket, "create_connection") as smtp:
            with patch("leadgen.verify._domain_resolves", return_value=True):
                verify.verify_email("hello@karam.com.eg")
        assert not smtp.called


class TestVerificationStage:
    def test_targets_come_only_from_what_was_observed(self):
        """Never a constructed address: a bounce from a guessed email is a worse
        first impression than no email at all."""
        lead = make_lead(phone_e164="+201001234567")
        WebsiteProfile.objects.create(lead=lead, emails=["info@karam.com.eg"])
        lead.refresh_from_db()

        targets = verification.targets_for(lead)
        assert (enums.VerificationKind.PHONE, "+201001234567") in targets
        assert (enums.VerificationKind.EMAIL, "info@karam.com.eg") in targets
        assert len(targets) == 2

    def test_email_count_is_capped(self):
        lead = make_lead()
        WebsiteProfile.objects.create(lead=lead, emails=[f"a{i}@karam.com.eg" for i in range(10)])
        lead.refresh_from_db()
        emails = [t for t in verification.targets_for(lead) if t[0] == "email"]
        assert len(emails) == verification.MAX_EMAILS_PER_LEAD

    def test_records_a_row_per_contact(self):
        lead = make_lead(phone_e164="+201001234567")
        WebsiteProfile.objects.create(lead=lead, emails=["info@karam.com.eg"])
        lead.refresh_from_db()

        with patch("leadgen.verify._domain_resolves", return_value=True):
            records = verification.verify_lead(lead)

        assert len(records) == 2
        assert all(r.status == enums.TaskStatus.COMPLETED for r in records)

    def test_re_running_updates_in_place(self):
        """A retried queue must not multiply its own backlog."""
        lead = make_lead(phone_e164="+201001234567")
        verification.verify_lead(lead)
        verification.verify_lead(lead)

        assert Verification.objects.filter(lead=lead).count() == 1
        assert Verification.objects.get(lead=lead).attempts == 2

    def test_offline_results_are_not_billed(self):
        """The fallback costs nothing and must not appear in the ledger as
        spend that never happened."""
        lead = make_lead(phone_e164="+201001234567")
        verification.verify_lead(lead)
        assert not ApiUsage.objects.exists()

    def test_lead_with_no_contacts_produces_no_rows(self):
        assert verification.verify_lead(make_lead()) == []


class TestScoringIntegration:
    def test_only_a_provider_confirmation_earns_the_verified_points(self):
        from leadgen import scoring

        lead = make_lead(phone_e164="+201001234567", reviews_count=900)

        verification.verify_lead(lead)  # offline → POSSIBLE
        lead.refresh_from_db()
        before = scoring.score_lead(lead)[0]

        Verification.objects.filter(lead=lead).update(
            result=enums.VerificationResult.VERIFIED,
            provider=enums.ApiProvider.TWILIO_LOOKUP,
        )
        lead.refresh_from_db()
        after = scoring.score_lead(lead)[0]

        assert after - before == scoring.PHONE_VERIFIED_POINTS

    def test_breakdown_distinguishes_unchecked_from_unconfirmed(self):
        from leadgen import scoring

        lead = make_lead(phone_e164="+201001234567")
        unchecked = next(r for r in scoring.score_lead(lead)[2] if r["key"] == "phone_verified")
        assert unchecked["detail"] == "Not verified yet"

        verification.verify_lead(lead)
        lead.refresh_from_db()
        checked = next(r for r in scoring.score_lead(lead)[2] if r["key"] == "phone_verified")
        assert "unconfirmed" in checked["detail"]
