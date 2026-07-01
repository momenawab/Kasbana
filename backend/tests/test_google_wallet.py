"""Tests for the Google Wallet backend (offline parts: builders + save URL)."""

from __future__ import annotations

import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tests import factories
from wallets.google import builders, client
from wallets.google.client import GoogleWalletBackend

pytestmark = pytest.mark.django_db

ISSUER = "1234567890"


@pytest.fixture
def google_creds(tmp_path, settings):
    """Generate a throwaway RSA service-account key and point settings at it."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    sa_file = tmp_path / "sa.json"
    sa_file.write_text(json.dumps({"client_email": "svc@test.iam", "private_key": pem}))

    settings.WALLET = {
        **settings.WALLET,
        "GOOGLE": {"ISSUER_ID": ISSUER, "SA_KEY_PATH": str(sa_file)},
    }
    return pem, key.public_key()


def test_ids_are_namespaced_under_issuer(settings, google_creds):
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    assert builders.class_id_for(card).startswith(f"{ISSUER}.")
    assert builders.object_id_for(cc).startswith(f"{ISSUER}.")


def test_loyalty_object_carries_balance_and_barcode(settings, google_creds):
    card = factories.CardFactory(stamps_required=8)
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=3)
    obj = builders.build_loyalty_object(cc)
    assert obj["loyaltyPoints"]["balance"]["int"] == 3
    assert obj["secondaryLoyaltyPoints"]["balance"]["int"] == 8
    assert obj["barcode"]["value"].startswith("WLA")
    assert obj["classId"] == builders.class_id_for(card)
    assert obj["state"] == "ACTIVE"


def test_points_card_labels_balance_as_points(settings, google_creds):
    from core.enums import CardType

    card = factories.CardFactory(type=CardType.POINTS, stamps_required=100)
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=40)
    assert builders.build_loyalty_object(cc)["loyaltyPoints"]["label"] == "Points"


def test_completed_card_object_is_expired(settings, google_creds):
    from core.enums import CustomerCardStatus

    card = factories.CardFactory(stamps_required=5, single_use=True)
    cc = factories.CustomerCardFactory(
        card=card, merchant=card.merchant, status=CustomerCardStatus.COMPLETED
    )
    assert builders.build_loyalty_object(cc)["state"] == "EXPIRED"


def test_save_url_is_signed_jwt(settings, google_creds):
    _pem, public_key = google_creds
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)

    url = client.build_save_url(cc)
    assert url is not None
    assert url.startswith("https://pay.google.com/gp/v/save/")

    token = url.rsplit("/", 1)[-1]
    decoded = jwt.decode(token, public_key, algorithms=["RS256"], audience="google")
    assert decoded["typ"] == "savetowallet"
    assert decoded["iss"] == "svc@test.iam"
    assert decoded["payload"]["loyaltyObjects"][0]["id"] == builders.object_id_for(cc)


def test_save_url_none_without_credentials(settings):
    settings.WALLET = {**settings.WALLET, "GOOGLE": {"ISSUER_ID": "", "SA_KEY_PATH": ""}}
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    assert client.build_save_url(cc) is None


def test_backend_degrades_without_credentials(settings):
    settings.WALLET = {**settings.WALLET, "GOOGLE": {"ISSUER_ID": "", "SA_KEY_PATH": ""}}
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    backend = GoogleWalletBackend()
    assert backend.provision(cc) is None
    backend.push_update(cc)  # no-op, must not raise
