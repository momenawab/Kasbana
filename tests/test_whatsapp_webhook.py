import pytest
from rest_framework.test import APIClient

from whatsapp.webhook import valid_signature

VERIFY_URL = "/api/v1/webhooks/whatsapp/"


def test_invalid_webhook_signature_is_rejected(settings):
    settings.WHATSAPP_APP_SECRET = "secret"
    assert not valid_signature(b"{}", "sha256=wrong")


@pytest.mark.django_db
def test_verify_echoes_the_challenge_as_raw_bytes(settings):
    """Meta compares the body byte-for-byte with the challenge it sent.

    DRF's Response runs the JSONRenderer even when handed content_type=
    "text/plain", which returned b'"1158201444"' — quotes included — and Meta
    rejected the subscription with "callback URL or verify token couldn't be
    validated" despite the 200. Pin the raw body so that cannot come back.
    """
    settings.WHATSAPP_VERIFY_TOKEN = "tok"
    response = APIClient().get(
        VERIFY_URL,
        {"hub.mode": "subscribe", "hub.verify_token": "tok", "hub.challenge": "1158201444"},
    )
    assert response.status_code == 200
    assert response.content == b"1158201444"  # NOT b'"1158201444"'


@pytest.mark.django_db
def test_verify_rejects_a_wrong_token(settings):
    settings.WHATSAPP_VERIFY_TOKEN = "tok"
    response = APIClient().get(
        VERIFY_URL,
        {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "x"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_verify_fails_closed_when_no_token_is_configured(settings):
    """An unconfigured deployment must not validate an empty verify_token —
    otherwise anyone could subscribe their own endpoint to the app."""
    settings.WHATSAPP_VERIFY_TOKEN = ""
    response = APIClient().get(VERIFY_URL, {"hub.mode": "subscribe", "hub.verify_token": ""})
    assert response.status_code == 403
