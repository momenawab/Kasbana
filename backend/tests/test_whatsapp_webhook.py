from whatsapp.webhook import valid_signature


def test_invalid_webhook_signature_is_rejected(settings):
    settings.WHATSAPP_APP_SECRET = "secret"
    assert not valid_signature(b"{}", "sha256=wrong")
