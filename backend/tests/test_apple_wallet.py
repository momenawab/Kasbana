"""Tests for the Apple Wallet backend: pass build/sign + the 5 web-service endpoints."""

from __future__ import annotations

import datetime
import io
import json
import zipfile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from core.enums import WalletPlatform
from core.models import WalletRegistration
from tests import factories
from wallets.apple import passdata
from wallets.apple.signing import build_pkpass

pytestmark = pytest.mark.django_db


def _self_signed_p12(password: str = "") -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Stampn Test Pass")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    enc = (
        serialization.BestAvailableEncryption(password.encode())
        if password
        else serialization.NoEncryption()
    )
    return pkcs12.serialize_key_and_certificates(b"stampn", key, cert, None, enc)


@pytest.fixture
def apple_configured(tmp_path, settings):
    p12 = tmp_path / "pass.p12"
    p12.write_bytes(_self_signed_p12(password="secret"))
    settings.BASE_URL = "https://api.stampn.net"
    settings.WALLET = {
        **settings.WALLET,
        "APPLE": {
            "PASS_TYPE_ID": "pass.net.stampn.loyalty",
            "TEAM_ID": "TEAM123456",
            "PASS_CERT_PATH": str(p12),
            "PASS_CERT_PASSWORD": "secret",
            "WWDR_CERT_PATH": "",
            "APNS_USE_SANDBOX": True,
        },
    }
    return settings


@pytest.fixture
def customer_card(apple_configured):
    card = factories.CardFactory(stamps_required=6)
    return factories.CustomerCardFactory(card=card, merchant=card.merchant, stamp_count=2)


# ── pass.json + signing ──────────────────────────────────────────────────────
def test_pass_json_has_required_fields(customer_card):
    p = passdata.build_pass_json(customer_card)
    assert p["serialNumber"] == str(customer_card.id)
    assert p["passTypeIdentifier"] == "pass.net.stampn.loyalty"
    assert p["teamIdentifier"] == "TEAM123456"
    assert p["authenticationToken"] == customer_card.auth_token
    assert p["webServiceURL"] == "https://api.stampn.net/api/v1/wallet/apple"
    assert p["storeCard"]["primaryFields"][0]["value"] == 2


def test_pass_json_has_no_message_field_without_a_message(customer_card):
    p = passdata.build_pass_json(customer_card)
    assert p["storeCard"]["backFields"] == []


def test_pass_json_surfaces_latest_message_with_change_message(customer_card):
    from wallets.models import WalletMessage

    WalletMessage.objects.create(customer_card=customer_card, body="Old offer")
    WalletMessage.objects.create(customer_card=customer_card, title="Promo", body="Free coffee!")

    back = passdata.build_pass_json(customer_card)["storeCard"]["backFields"]
    assert len(back) == 1
    field = back[0]
    assert field["value"] == "Free coffee!"  # newest wins
    assert field["label"] == "Promo"
    # changeMessage is what makes iOS show a lock-screen notification on change.
    assert field["changeMessage"] == "%@"


def test_build_pkpass_is_valid_zip_with_matching_manifest(customer_card):
    raw = build_pkpass(customer_card)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert {"pass.json", "manifest.json", "signature", "icon.png"} <= names

    manifest = json.loads(zf.read("manifest.json"))
    import hashlib

    for fname, digest in manifest.items():
        assert hashlib.sha1(zf.read(fname)).hexdigest() == digest
    assert len(zf.read("signature")) > 0


# ── web service ──────────────────────────────────────────────────────────────
def _auth(cc):
    return {"HTTP_AUTHORIZATION": f"ApplePass {cc.auth_token}"}


def _base(cc):
    pt = "pass.net.stampn.loyalty"
    return f"/api/v1/wallet/apple/v1/devices/DEV123/registrations/{pt}/{cc.id}"


def test_register_requires_auth(client, customer_card):
    resp = client.post(
        _base(customer_card), data=json.dumps({"pushToken": "tok"}), content_type="application/json"
    )
    assert resp.status_code == 401


def test_register_then_reregister(client, customer_card):
    url = _base(customer_card)
    r1 = client.post(
        url,
        data=json.dumps({"pushToken": "tok1"}),
        content_type="application/json",
        **_auth(customer_card),
    )
    assert r1.status_code == 201
    reg = WalletRegistration.objects.get(customer_card=customer_card, device_library_id="DEV123")
    assert reg.platform == WalletPlatform.APPLE
    assert reg.push_token == "tok1"

    r2 = client.post(
        url,
        data=json.dumps({"pushToken": "tok2"}),
        content_type="application/json",
        **_auth(customer_card),
    )
    assert r2.status_code == 200
    reg.refresh_from_db()
    assert reg.push_token == "tok2"


def test_list_updated_serials(client, customer_card):
    client.post(
        _base(customer_card),
        data=json.dumps({"pushToken": "tok"}),
        content_type="application/json",
        **_auth(customer_card),
    )
    pt = "pass.net.stampn.loyalty"
    list_url = f"/api/v1/wallet/apple/v1/devices/DEV123/registrations/{pt}"
    resp = client.get(list_url)
    assert resp.status_code == 200
    body = resp.json()
    assert str(customer_card.id) in body["serialNumbers"]
    assert "lastUpdated" in body

    # Nothing newer than 'now' -> 204.
    resp2 = client.get(list_url, {"passesUpdatedSince": body["lastUpdated"]})
    assert resp2.status_code == 204


def test_get_pass_requires_auth_and_returns_pkpass(client, customer_card):
    pt = "pass.net.stampn.loyalty"
    url = f"/api/v1/wallet/apple/v1/passes/{pt}/{customer_card.id}"
    assert client.get(url).status_code == 401

    resp = client.get(url, **_auth(customer_card))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.apple.pkpass"
    assert zipfile.ZipFile(io.BytesIO(resp.content)).read("pass.json")


def test_unregister_device(client, customer_card):
    client.post(
        _base(customer_card),
        data=json.dumps({"pushToken": "tok"}),
        content_type="application/json",
        **_auth(customer_card),
    )
    resp = client.delete(_base(customer_card), **_auth(customer_card))
    assert resp.status_code == 200
    assert not WalletRegistration.objects.get(customer_card=customer_card).is_active


def test_log_endpoint(client):
    resp = client.post(
        "/api/v1/wallet/apple/v1/log",
        data=json.dumps({"logs": ["hi"]}),
        content_type="application/json",
    )
    assert resp.status_code == 200


def test_download_pass(client, customer_card):
    resp = client.get(f"/api/v1/wallet/apple/download/{customer_card.id}")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/vnd.apple.pkpass"


def test_download_pass_503_without_certs(client, settings):
    settings.WALLET = {
        **settings.WALLET,
        "APPLE": {"PASS_TYPE_ID": "", "TEAM_ID": "", "PASS_CERT_PATH": ""},
    }
    card = factories.CardFactory()
    cc = factories.CustomerCardFactory(card=card, merchant=card.merchant)
    resp = client.get(f"/api/v1/wallet/apple/download/{cc.id}")
    assert resp.status_code == 503
