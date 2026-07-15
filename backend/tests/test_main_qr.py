"""Tests for the merchant main QR (finalize Phase A).

One printed QR, re-pointable at any program. Covers the ``MerchantEnrollLink``
model, ``resolve_join_target`` (card token vs merchant token, and every reason a
merchant token must 404), the ``/settings/main-qr`` endpoints, and the join +
referral flow through the merchant token.
"""

from __future__ import annotations

import pytest

from core.enums import CardStatus
from tests import factories

pytestmark = pytest.mark.django_db


def _link(merchant):
    from enrollment.tokens import get_or_issue_merchant_link

    return get_or_issue_merchant_link(merchant)


# ── model + issuance ──────────────────────────────────────────────────────────


def test_get_or_issue_merchant_link_is_idempotent(merchant):
    first = _link(merchant)
    second = _link(merchant)
    assert first.pk == second.pk
    assert first.token == second.token


def test_link_survives_deletion_of_its_primary_card(merchant, card):
    link = _link(merchant)
    link.primary_card = card
    link.save()

    card.delete()

    link.refresh_from_db()
    assert link.primary_card is None  # SET_NULL, not cascade
    assert link.token  # the printed token is untouched


def test_rotate_mints_a_new_token(merchant):
    from enrollment.tokens import rotate_merchant_link

    old = _link(merchant).token
    assert rotate_merchant_link(merchant).token != old


# ── resolve_join_target ───────────────────────────────────────────────────────


def test_resolves_a_card_token_to_its_own_card(card):
    from enrollment.tokens import get_or_issue_enrollment_token, resolve_join_target

    token = get_or_issue_enrollment_token(card).token
    merchant, resolved = resolve_join_target(token)
    assert resolved == card
    assert merchant == card.merchant


def test_resolves_a_merchant_token_to_the_primary_card(merchant, card):
    from enrollment.tokens import resolve_join_target

    link = _link(merchant)
    link.primary_card = card
    link.save()

    resolved_merchant, resolved_card = resolve_join_target(link.token)
    assert resolved_card == card
    assert resolved_merchant == merchant


def test_merchant_token_with_no_primary_card_is_not_resolvable(merchant):
    """Never guess a card — an un-elected main QR must 404, not pick one."""
    from enrollment.tokens import resolve_join_target

    assert resolve_join_target(_link(merchant).token) is None


@pytest.mark.parametrize("status", [CardStatus.DRAFT, CardStatus.ARCHIVED])
def test_merchant_token_pointing_at_an_inactive_card_is_not_resolvable(merchant, status):
    from enrollment.tokens import resolve_join_target

    card = factories.CardFactory(merchant=merchant, status=status)
    link = _link(merchant)
    link.primary_card = card
    link.save()

    assert resolve_join_target(link.token) is None


def test_deactivated_link_is_not_resolvable(merchant, card):
    from enrollment.tokens import resolve_join_target

    link = _link(merchant)
    link.primary_card = card
    link.is_active = False
    link.save()

    assert resolve_join_target(link.token) is None


def test_unknown_token_is_not_resolvable():
    from enrollment.tokens import resolve_join_target

    assert resolve_join_target("nope-not-a-token") is None


def test_expired_card_token_still_raises_410(card):
    """Card-token TTL behavior is unchanged by the merchant-token fallback."""
    from datetime import timedelta

    from django.utils import timezone

    from common.errors import TokenExpired
    from enrollment.tokens import get_or_issue_enrollment_token, resolve_join_target

    token = get_or_issue_enrollment_token(card)
    token.expires_at = timezone.now() - timedelta(days=1)
    token.save()

    with pytest.raises(TokenExpired):
        resolve_join_target(token.token)


# ── public join flow through the merchant token ───────────────────────────────


def test_enroll_through_the_main_qr_joins_the_primary_card(api_client, merchant, card):
    from core.models import CustomerCard

    link = _link(merchant)
    link.primary_card = card
    link.save()

    landing = api_client.get(f"/api/v1/enroll/{link.token}")
    assert landing.status_code == 200
    assert landing.json()["card_name"] == card.name

    joined = api_client.post(
        f"/api/v1/enroll/{link.token}",
        {"customer_phone": "+201000000099", "consent": True},
        format="json",
    )
    assert joined.status_code == 201
    assert CustomerCard.objects.filter(card=card, customer_phone="+201000000099").exists()


def test_switching_the_primary_card_re_points_the_same_token(api_client, merchant, card):
    """The whole point of the feature: same printed QR, different program."""
    from core.models import CustomerCard

    other = factories.CardFactory(merchant=merchant, name="Second program")
    link = _link(merchant)
    link.primary_card = card
    link.save()

    api_client.post(
        f"/api/v1/enroll/{link.token}",
        {"customer_phone": "+201000000001", "consent": True},
        format="json",
    )

    link.primary_card = other
    link.save()

    api_client.post(
        f"/api/v1/enroll/{link.token}",
        {"customer_phone": "+201000000002", "consent": True},
        format="json",
    )

    assert CustomerCard.objects.filter(card=card).count() == 1
    assert CustomerCard.objects.filter(card=other).count() == 1


def test_enroll_through_an_unelected_main_qr_404s(api_client, merchant):
    assert api_client.get(f"/api/v1/enroll/{_link(merchant).token}").status_code == 404


def test_referral_url_minted_from_the_main_qr_stays_on_the_main_qr(api_client, merchant):
    """Otherwise a referred friend lands on a card token, and the referrer's
    shared link would rot the moment the merchant switches programs."""
    card = factories.CardFactory(merchant=merchant, referral_enabled=True)
    link = _link(merchant)
    link.primary_card = card
    link.save()

    body = api_client.post(
        f"/api/v1/enroll/{link.token}",
        {"customer_phone": "+201000000055", "consent": True},
        format="json",
    ).json()

    assert f"/enroll/{link.token}?ref=" in body["referral_url"]


# ── dashboard endpoints ───────────────────────────────────────────────────────


def test_get_main_qr_returns_the_link_and_no_assets_when_unelected(auth_client, merchant):
    body = auth_client.get("/api/v1/settings/main-qr").json()
    assert body["primary_card"] is None
    assert body["token"]
    assert body["join_url"].endswith(f"/enroll/{body['token']}")
    assert body["qr_svg"] == ""  # nothing to render a QR *for* yet


def test_get_main_qr_renders_assets_once_a_card_is_elected(
    auth_client, merchant, card, settings, tmpdir
):
    settings.MEDIA_ROOT = str(tmpdir)
    link = _link(merchant)
    link.primary_card = card
    link.save()

    body = auth_client.get("/api/v1/settings/main-qr").json()
    assert body["primary_card"]["id"] == str(card.id)
    assert body["qr_svg"].startswith("<svg")
    assert f"posters/main_{merchant.id}_" in body["poster_pdf_url"]


def test_main_qr_poster_does_not_evict_the_cards_own_poster(
    auth_client, merchant, card, settings, tmpdir
):
    """Both posters render the same card at different join URLs. A shared
    storage key would make each request's prune sweep delete the other's file."""
    from django.core.files.storage import default_storage

    settings.MEDIA_ROOT = str(tmpdir)
    link = _link(merchant)
    link.primary_card = card
    link.save()

    card_poster = auth_client.get(f"/api/v1/cards/{card.id}/qr").json()["poster_pdf_url"]
    main_poster = auth_client.get("/api/v1/settings/main-qr").json()["poster_pdf_url"]

    def path(url):
        return url.split(settings.MEDIA_URL, 1)[1]

    assert card_poster != main_poster
    assert default_storage.exists(path(card_poster))
    assert default_storage.exists(path(main_poster))


def test_patch_elects_a_card(auth_client, merchant, card):
    body = auth_client.patch(
        "/api/v1/settings/main-qr", {"primary_card_id": str(card.id)}, format="json"
    ).json()
    assert body["primary_card"]["id"] == str(card.id)
    assert _link(merchant).primary_card == card


def test_patch_null_unelects(auth_client, merchant, card):
    link = _link(merchant)
    link.primary_card = card
    link.save()

    body = auth_client.patch(
        "/api/v1/settings/main-qr", {"primary_card_id": None}, format="json"
    ).json()
    assert body["primary_card"] is None


@pytest.mark.parametrize("status", [CardStatus.DRAFT, CardStatus.ARCHIVED])
def test_patch_rejects_an_inactive_card(auth_client, merchant, status):
    card = factories.CardFactory(merchant=merchant, status=status)
    res = auth_client.patch(
        "/api/v1/settings/main-qr", {"primary_card_id": str(card.id)}, format="json"
    )
    assert res.status_code == 400


def test_patch_rejects_another_merchants_card(auth_client, merchant):
    """Cross-tenant ids must be indistinguishable from missing ones."""
    foreign = factories.CardFactory()
    res = auth_client.patch(
        "/api/v1/settings/main-qr", {"primary_card_id": str(foreign.id)}, format="json"
    )
    assert res.status_code == 404


def test_main_qr_is_tenancy_scoped(auth_client, merchant):
    """Merchant A's GET must mint/return A's link, never B's."""
    other = factories.MerchantFactory()
    other_link = _link(other)

    body = auth_client.get("/api/v1/settings/main-qr").json()
    assert body["token"] != other_link.token


def test_rotate_changes_the_token_and_kills_the_old_one(auth_client, api_client, merchant, card):
    link = _link(merchant)
    link.primary_card = card
    link.save()
    old_token = link.token

    new_token = auth_client.post("/api/v1/settings/main-qr/rotate").json()["token"]
    assert new_token != old_token

    assert api_client.get(f"/api/v1/enroll/{old_token}").status_code == 404
    assert api_client.get(f"/api/v1/enroll/{new_token}").status_code == 200


def test_main_qr_requires_auth(api_client):
    assert api_client.get("/api/v1/settings/main-qr").status_code == 401
