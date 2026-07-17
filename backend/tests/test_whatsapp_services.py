"""WhatsApp phone-verification service tests.

These exercise ``send_otp`` and ``verify_otp`` end to end — the paths the
original bundle's tests never touched, which is how a crash-on-every-send and a
cross-process expiry bug both shipped unnoticed.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from whatsapp.exceptions import OTPInvalid, OTPRateLimited
from whatsapp.models import WhatsAppMessageLog
from whatsapp.services import OTPService, link_phone
from whatsapp.utils import normalize_phone

pytestmark = pytest.mark.django_db
User = get_user_model()
PHONE = "+201000000000"


class FakeClient:
    """Captures the OTP that ``send_otp`` passes to the transport, so a test can
    read the code the way the real WhatsApp message would deliver it."""

    def __init__(self):
        self.sent = []

    def send_template(self, to, template_name, language, parameters):
        self.sent.append({"to": to, "otp": parameters[0]})
        return {"messages": [{"id": f"wamid.{len(self.sent)}"}]}


@pytest.fixture(autouse=True)
def locmem_cache(settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()


def test_phone_normalizes_and_otp_is_six_digits():
    assert normalize_phone("+20 1000000000") == "+201000000000"
    code = OTPService(client=FakeClient()).generate_otp(PHONE)
    assert code.isdigit() and len(code) == 6


def test_send_otp_delivers_a_code_and_logs_it():
    """The regression test for the original showstopper: _check_limits called
    _key('hour') without the phone argument, so every send raised TypeError."""
    client = FakeClient()
    OTPService(client=client).send_otp(PHONE)

    assert len(client.sent) == 1
    assert client.sent[0]["to"] == PHONE
    log = WhatsAppMessageLog.objects.get()
    assert log.message_id == "wamid.1"
    assert PHONE[3:] not in log.phone_masked  # the raw number is never stored


def test_verify_returns_tokens_only_for_a_linked_active_user():
    user = User.objects.create_user(username="u1", email="u1@x.com")
    link_phone(user, PHONE)

    client = FakeClient()
    service = OTPService(client=client)
    service.send_otp(PHONE)
    otp = client.sent[0]["otp"]

    tokens = service.verify_otp(PHONE, otp)
    assert tokens["access"] and tokens["refresh"]


def test_an_unknown_number_gets_no_tokens_even_with_the_right_code():
    """An OTP proves control of a phone; it must not create or seize an account."""
    client = FakeClient()
    service = OTPService(client=client)
    service.send_otp(PHONE)
    otp = client.sent[0]["otp"]

    with pytest.raises(OTPInvalid):
        service.verify_otp(PHONE, otp)


def test_a_wrong_code_is_rejected_and_burns_after_three_tries():
    user = User.objects.create_user(username="u2", email="u2@x.com")
    link_phone(user, PHONE)
    client = FakeClient()
    service = OTPService(client=client)
    service.send_otp(PHONE)

    for _ in range(3):
        with pytest.raises(OTPInvalid):
            service.verify_otp(PHONE, "000000")
    # Fourth attempt — even the correct code is now refused; the code is burned.
    with pytest.raises(OTPRateLimited):
        service.verify_otp(PHONE, client.sent[0]["otp"])


def test_a_used_code_cannot_be_replayed():
    user = User.objects.create_user(username="u3", email="u3@x.com")
    link_phone(user, PHONE)
    client = FakeClient()
    service = OTPService(client=client)
    service.send_otp(PHONE)
    otp = client.sent[0]["otp"]

    service.verify_otp(PHONE, otp)  # first use succeeds
    with pytest.raises(OTPInvalid):
        service.verify_otp(PHONE, otp)  # replay fails


def test_a_second_request_within_the_cooldown_is_rate_limited():
    service = OTPService(client=FakeClient())
    service.send_otp(PHONE)
    with pytest.raises(OTPRateLimited):
        service.send_otp(PHONE)


def test_link_phone_normalizes_and_is_idempotent():
    user = User.objects.create_user(username="u4", email="u4@x.com")
    a = link_phone(user, "+20 1000000000")
    b = link_phone(user, "+201000000000")
    assert a.phone == "+201000000000"
    assert a.pk == b.pk  # update_or_create, one identity per user
