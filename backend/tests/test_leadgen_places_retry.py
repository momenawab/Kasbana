"""How the Places client handles failure — the part that a live 429 exposed.

A rate limit is not a transient error, and treating it like one is expensive:
every attempt is a billed call, so retrying a 429 three times turns two real
queries into six wasted ones and can drain a small daily quota in retries. That
is exactly what happened in production — a job reported "0 businesses in 6
billed calls", all 429. These tests pin the corrected behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from leadgen.places import PlacesClient, PlacesError, _retry_after_seconds


def response(status: int, *, body: str = "{}", headers: dict | None = None) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = body
    r.headers = headers or {}
    r.json.return_value = {"places": []}
    return r


@pytest.fixture(autouse=True)
def no_pacing(settings):
    """Pacing sleeps real seconds; switch it off so tests are instant. The pacing
    behaviour itself is asserted separately with a patched clock."""
    settings.LEADGEN_PLACES_MIN_INTERVAL_S = 0
    settings.LEADGEN_PLACES_RETRY_AFTER_CAP_S = 10


def client() -> PlacesClient:
    return PlacesClient(api_key="test-key")


class TestRateLimit:
    def test_a_429_is_not_retried_three_times(self):
        """The bug: three attempts, three billed calls, none able to succeed
        inside seconds. A 429 with no short Retry-After must cost one call."""
        c = client()
        with patch("httpx.Client.post", return_value=response(429, body="quota exceeded")) as post:
            with pytest.raises(PlacesError, match="rate-limited"):
                c._post("url", {}, "mask")

        assert post.call_count == 1
        assert c.billed_calls == 1

    def test_the_error_names_the_fix(self):
        """An operator reading the job log should learn what to do, not just
        that something failed."""
        c = client()
        with patch("httpx.Client.post", return_value=response(429)):
            with pytest.raises(PlacesError, match="per-minute quota"):
                c._post("url", {}, "mask")

    def test_a_short_retry_after_is_honoured_once(self):
        """When Google says "wait 2s" and then would succeed, do exactly that —
        one wait, one retry, no more."""
        c = client()
        responses = [response(429, headers={"Retry-After": "2"}), response(200)]
        with patch("httpx.Client.post", side_effect=responses), patch(
            "leadgen.places.time.sleep"
        ) as slept:
            result = c._post("url", {}, "mask")

        assert result == {"places": []}
        assert c.billed_calls == 2
        slept.assert_called_once_with(2.0)

    def test_a_retry_after_beyond_the_cap_is_not_waited(self, settings):
        """A 60s reset is longer than a job should hold the pipeline for."""
        settings.LEADGEN_PLACES_RETRY_AFTER_CAP_S = 10
        c = client()
        with patch(
            "httpx.Client.post", return_value=response(429, headers={"Retry-After": "60"})
        ) as post, patch("leadgen.places.time.sleep") as slept:
            with pytest.raises(PlacesError, match="rate-limited"):
                c._post("url", {}, "mask")

        assert post.call_count == 1
        slept.assert_not_called()


class TestOtherFailures:
    def test_a_400_fails_immediately_without_retrying(self):
        """A bad request will be bad every time — no point burning attempts."""
        c = client()
        with patch("httpx.Client.post", return_value=response(400, body="bad")) as post:
            with pytest.raises(PlacesError, match="rejected the request"):
                c._post("url", {}, "mask")
        assert post.call_count == 1

    def test_a_403_reports_a_key_restriction(self):
        c = client()
        with patch("httpx.Client.post", return_value=response(403, body="denied")):
            with pytest.raises(PlacesError, match="restrictions"):
                c._post("url", {}, "mask")

    def test_a_5xx_is_retried_with_backoff(self):
        """Server errors are genuinely transient — the short backoff is right."""
        c = client()
        responses = [response(503), response(503), response(200)]
        with patch("httpx.Client.post", side_effect=responses), patch(
            "leadgen.places.time.sleep"
        ):
            result = c._post("url", {}, "mask")
        assert result == {"places": []}
        assert c.billed_calls == 3

    def test_a_network_error_is_retried(self):
        c = client()
        with patch(
            "httpx.Client.post",
            side_effect=[httpx.ConnectError("down"), httpx.ConnectError("down"), response(200)],
        ), patch("leadgen.places.time.sleep"):
            assert c._post("url", {}, "mask") == {"places": []}

    def test_a_missing_key_raises_before_any_call(self):
        from leadgen.places import PlacesNotConfigured

        with patch("httpx.Client.post") as post:
            with pytest.raises(PlacesNotConfigured):
                PlacesClient(api_key="")._post("url", {}, "mask")
        assert not post.called


class TestPacing:
    def test_calls_are_spaced_by_the_configured_interval(self, settings):
        """The prevention: a job's burst is spread out so it never trips the
        per-minute quota in the first place."""
        settings.LEADGEN_PLACES_MIN_INTERVAL_S = 0.6
        c = client()

        clock = {"t": 100.0}
        with patch("leadgen.places.time.monotonic", lambda: clock["t"]), patch(
            "leadgen.places.time.sleep"
        ) as slept, patch("httpx.Client.post", return_value=response(200)):
            c._last_call_at = 100.0  # a call just happened
            c._pace()

        # Only 0s have passed, so it must wait the full interval.
        slept.assert_called_once()
        assert slept.call_args[0][0] == pytest.approx(0.6)

    def test_no_wait_when_enough_time_has_already_passed(self, settings):
        settings.LEADGEN_PLACES_MIN_INTERVAL_S = 0.6
        c = client()
        clock = {"t": 200.0}
        with patch("leadgen.places.time.monotonic", lambda: clock["t"]), patch(
            "leadgen.places.time.sleep"
        ) as slept:
            c._last_call_at = 100.0  # 100s ago — well past the interval
            c._pace()
        slept.assert_not_called()


class TestRetryAfterHeader:
    def test_integer_seconds(self):
        assert _retry_after_seconds(response(429, headers={"Retry-After": "5"})) == 5.0

    def test_http_date_is_ignored(self):
        """A date parses to the ~60s a per-minute quota needs, too long to hold."""
        r = response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        assert _retry_after_seconds(r) == 0.0

    def test_absent_header(self):
        assert _retry_after_seconds(response(429)) == 0.0
