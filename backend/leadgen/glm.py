"""Zhipu GLM client for AI enrichment.

Speaks the OpenAI-compatible chat-completions API, so this is a plain HTTP call
rather than a vendor SDK — one less dependency to track, and swapping in another
OpenAI-compatible provider is a base-URL change.

Two things this insists on:

* **Structured output, validated.** The model is asked for JSON and the response
  is parsed and coerced before it reaches the database. A model that returns
  prose, or a number where a string belongs, must fail loudly here rather than
  writing nonsense into columns a rep will read as fact.
* **Every call is priced.** Token counts come back on the response; the cost
  ledger is written from those rather than estimated from lead counts, because
  "why did yesterday cost that much" is only answerable from real usage.

Billing note: this needs a pay-as-you-go key. Zhipu's flat-rate Coding Plan is
licensed for approved coding tools, not production application traffic.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1"


class GlmError(RuntimeError):
    """Any failure reaching or understanding the model."""


class GlmNotConfigured(GlmError):
    """No API key. Distinct so the queue reports setup, not an outage."""


@dataclass
class GlmResult:
    data: dict
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def cost_usd(self) -> Decimal:
        """Priced from real token counts, at the configured contract rates.

        ``tokens_out`` is the provider's ``completion_tokens``, which already
        includes reasoning tokens — they are billed like any other output, so
        the cost is right without adding them separately.
        """
        rate_in = Decimal(str(settings.GLM_PRICE_PER_MTOK_IN))
        rate_out = Decimal(str(settings.GLM_PRICE_PER_MTOK_OUT))
        million = Decimal("1000000")
        return (
            Decimal(self.tokens_in) / million * rate_in
            + Decimal(self.tokens_out) / million * rate_out
        ).quantize(Decimal("0.000001"))


# Fences the model sometimes wraps JSON in despite being told not to.
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def extract_json(content: str) -> dict:
    """Parse the model's reply into a dict, tolerating a code fence.

    Tolerant of formatting, strict about type: anything that is not a JSON
    object raises. A model that answered in prose has not answered, and letting
    that through would write empty analysis rows that look like real ones.
    """
    if not content or not content.strip():
        raise GlmError("Model returned an empty response.")

    text = content.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GlmError(f"Model did not return valid JSON: {exc}. Got: {text[:200]}") from exc

    if not isinstance(parsed, dict):
        raise GlmError(f"Model returned {type(parsed).__name__}, expected a JSON object.")
    return parsed


class GlmClient:
    """One instance per enrichment run."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key if api_key is not None else settings.GLM_API_KEY
        self.model = model or settings.GLM_MODEL
        self.base_url = settings.GLM_BASE_URL.rstrip("/")
        self.timeout = settings.LEADGEN_AI_TIMEOUT

    def complete_json(self, *, system: str, user: str, max_tokens: int | None = None) -> GlmResult:
        """Ask for a JSON object and return it parsed, with usage.

        Temperature is low but not zero. Zero buys reproducibility we cannot use
        — the inputs differ for every business — while a little sampling avoids
        the degenerate repetition these models fall into on terse listings.
        """
        if not self.api_key:
            raise GlmNotConfigured(
                "GLM_API_KEY is not set. AI enrichment needs a pay-as-you-go key — "
                "a GLM Coding Plan subscription does not cover application traffic."
            )

        # GLM-5.2 is a reasoning model: it spends completion tokens thinking
        # before it writes anything, and those come out of the same budget. A
        # tight max_tokens is silently consumed by reasoning and returns empty
        # content — which looks like a broken model rather than a small budget.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens or settings.LEADGEN_AI_MAX_TOKENS,
            # Honoured by the OpenAI-compatible surface; the fence-tolerant
            # parser stays as a backstop for providers that ignore it.
            "response_format": {"type": "json_object"},
        }

        started = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise GlmError(f"Could not reach GLM: {exc}") from exc

        duration_ms = int((time.monotonic() - started) * 1000)

        if response.status_code == 401:
            raise GlmNotConfigured("GLM rejected the API key (401).")
        if response.status_code != 200:
            raise GlmError(f"GLM returned HTTP {response.status_code}: {response.text[:300]}")

        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise GlmError(f"Unexpected GLM response shape: {str(body)[:300]}") from exc

        usage = body.get("usage") or {}
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)

        # Distinguish "the model had nothing to say" from "the model never got
        # to the answer". Only the second is actionable, and only by raising the
        # budget — so say so rather than reporting an empty response.
        if not (content or "").strip() and reasoning:
            raise GlmError(
                f"Model used all {usage.get('completion_tokens', 0)} completion tokens on "
                f"reasoning ({reasoning}) and produced no answer. Raise LEADGEN_AI_MAX_TOKENS."
            )

        return GlmResult(
            data=extract_json(content),
            tokens_in=usage.get("prompt_tokens", 0) or 0,
            tokens_out=usage.get("completion_tokens", 0) or 0,
            duration_ms=duration_ms,
            model=body.get("model") or self.model,
            raw=body,
        )

    def ping(self) -> tuple[bool, str]:
        """Test Connection: a real, minimal call. Returns (ok, message).

        Deliberately makes a live request rather than checking that a key is
        non-empty — "configured" and "working" are different states, and the
        button exists to distinguish them.
        """
        try:
            # Not a tight budget: a reasoning model needs room to think even
            # for a trivial answer, and a too-small ping fails for a reason that
            # has nothing to do with whether the key works.
            result = self.complete_json(
                system="Reply with JSON only.",
                user='Return exactly {"ok": true}.',
                max_tokens=512,
            )
        except GlmNotConfigured as exc:
            return False, str(exc)
        except GlmError as exc:
            return False, str(exc)
        return True, f"{result.model} responded in {result.duration_ms} ms"
