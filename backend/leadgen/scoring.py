"""Fit scoring — how good a prospect a discovered business is, 0-100.

This is *not* ``console.crm.score_lead``. That one measures engagement: how hard
a rep has worked a lead, recomputed from the CRM timeline on every activity. It
answers "how close is this to closing". This one measures fit, from signals
observable before anyone has spoken to the business, and answers "is this worth
a call at all". A lead can be 95 here and 25 there on the same day, and both are
correct — which is exactly why the two never share a column.

Every signal returns a line in the breakdown, including the ones worth zero, so
a rep disputing a score sees which signals were checked and which were missing
rather than an unexplained number.

Weight design follows ``console.crm``'s precedent: the positives sum to exactly
100, so a full bar means every signal fired and the total needs no clamping.

One departure from the spec's table, deliberate: the spec puts the whole
20-point phone weight on "Verified Phone", and its positives sum to 95. Since
Hot starts at 90, that made Hot unreachable without verification — and in
Phase 1, where verification is not yet wired, *nothing* could have scored above
75 and the entire funnel would have read Cold. The weight is therefore split:
a valid, parseable number earns 8, and provider-confirmed reachability earns
the remaining 12. The useful property this buys is that **Hot now means
verified** — no lead reaches 90 on unverified signals alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from leadgen import enums

SCORE_MAX = 100


@dataclass(frozen=True)
class Signal:
    """One scored observation. ``points`` may be zero (checked, absent) or
    negative (a disqualifying finding)."""

    key: str
    label: str
    points: int
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "points": self.points,
            "detail": self.detail,
        }


# ── Weights ──────────────────────────────────────────────────────────────────
WEBSITE_POINTS = 10
EMAIL_POINTS = 10
INSTAGRAM_POINTS = 5
FACEBOOK_POINTS = 5
PHONE_VALID_POINTS = 8
PHONE_VERIFIED_POINTS = 12  # Phase 2 — awarded by the verification stage
DIGITAL_PRESENCE_POINTS = 5  # on a delivery/reservation platform already

# Graduated rather than the spec's single ">500 reviews" cliff. At a cliff, 499
# reviews scores 0 and 500 scores 15, which is noise masquerading as judgement;
# a busy neighbourhood cafe with 300 reviews is plainly a better prospect than
# one with 4, and the tiers say so.
REVIEW_TIERS: tuple[tuple[int, int], ...] = ((500, 15), (200, 10), (50, 5))
RATING_TIERS: tuple[tuple[float, int], ...] = ((4.5, 10), (4.0, 5))
# Branch count comes from the dedupe stage, which collapses a chain's listings
# into one lead. Multiple branches is the strongest single buying signal we can
# observe: it means budget, process, and a reason to want cross-branch loyalty.
BRANCH_TIERS: tuple[tuple[int, int], ...] = ((4, 20), (2, 10))

# Negatives. A business already running a loyalty programme is not worthless —
# it has proven it wants one — but it is a displacement sale, which is slower.
ALREADY_LOYALTY_PENALTY = -15
SPAM_PHONE_PENALTY = -50  # Phase 2 — set by the verification stage

# ── Labels ───────────────────────────────────────────────────────────────────
HOT_MIN = 90
WARM_MIN = 70
COLD_MIN = 50


def label_for(score: int) -> str:
    if score >= HOT_MIN:
        return enums.ScoreLabel.HOT
    if score >= WARM_MIN:
        return enums.ScoreLabel.WARM
    if score >= COLD_MIN:
        return enums.ScoreLabel.COLD
    return enums.ScoreLabel.IGNORE


def _tiered(value: float, tiers: tuple[tuple[float, int], ...]) -> int:
    """Points for the highest tier ``value`` reaches. Tiers are descending."""
    for threshold, points in tiers:
        if value >= threshold:
            return points
    return 0


def score_lead(lead) -> tuple[int, str, list[dict]]:
    """Return ``(score, label, breakdown)`` for a ``GeneratedLead``.

    Pure and idempotent — it reads the lead and its already-loaded relations and
    derives everything from scratch, so re-scoring after any enrichment stage is
    always safe and never double-counts.

    A permanently closed business short-circuits to zero. It is not a weak
    prospect, it is not a prospect: letting it accumulate points for its website
    and 900 reviews would float a dead business to the top of the queue.
    """
    if lead.business_status == "CLOSED_PERMANENTLY":
        closed = Signal(
            key="closed",
            label="Permanently closed",
            points=0,
            detail="Google reports this business as permanently closed.",
        )
        return 0, enums.ScoreLabel.IGNORE, [closed.as_dict()]

    signals: list[Signal] = []

    # ── Reachability ─────────────────────────────────────────────────────────
    signals.append(
        Signal(
            "phone_valid",
            "Valid phone number",
            PHONE_VALID_POINTS if lead.phone_e164 else 0,
            lead.phone_e164 or "No parseable number on the listing",
        )
    )

    website = bool(lead.website_domain)
    signals.append(
        Signal(
            "website",
            "Has a website",
            WEBSITE_POINTS if website else 0,
            lead.website_domain or "No website on the listing",
        )
    )

    profile = getattr(lead, "website_profile", None)
    emails = list(profile.emails) if profile else []
    signals.append(
        Signal(
            "email",
            "Published email address",
            EMAIL_POINTS if emails else 0,
            emails[0] if emails else "No email found on the website",
        )
    )

    # ── Social presence ──────────────────────────────────────────────────────
    # ``socials`` is prefetched by the scoring stage; falling back to a query
    # here would make this N+1 across a 1,000-lead job.
    platforms = {s.platform for s in lead.socials.all()}
    signals.append(
        Signal(
            "instagram",
            "Instagram profile",
            INSTAGRAM_POINTS if enums.SocialPlatform.INSTAGRAM in platforms else 0,
            "Linked from the website" if enums.SocialPlatform.INSTAGRAM in platforms else "None found",
        )
    )
    signals.append(
        Signal(
            "facebook",
            "Facebook page",
            FACEBOOK_POINTS if enums.SocialPlatform.FACEBOOK in platforms else 0,
            "Linked from the website" if enums.SocialPlatform.FACEBOOK in platforms else "None found",
        )
    )

    # ── Traction ─────────────────────────────────────────────────────────────
    review_points = _tiered(lead.reviews_count, REVIEW_TIERS)
    signals.append(
        Signal("reviews", "Review volume", review_points, f"{lead.reviews_count} reviews")
    )

    rating = float(lead.rating) if lead.rating is not None else 0.0
    signals.append(
        Signal(
            "rating",
            "Google rating",
            _tiered(rating, RATING_TIERS),
            f"{rating:.1f} stars" if rating else "Not yet rated",
        )
    )

    branch_points = _tiered(lead.branch_count, BRANCH_TIERS)
    signals.append(
        Signal(
            "branches",
            "Multiple branches",
            branch_points,
            f"{lead.branch_count} location{'s' if lead.branch_count != 1 else ''} found",
        )
    )

    # ── Digital maturity ─────────────────────────────────────────────────────
    on_platform = bool(profile and (profile.delivery_platforms or profile.reservation_platforms))
    signals.append(
        Signal(
            "digital_presence",
            "Already on a delivery or booking platform",
            DIGITAL_PRESENCE_POINTS if on_platform else 0,
            ", ".join((profile.delivery_platforms + profile.reservation_platforms))
            if on_platform
            else "None detected",
        )
    )

    # ── Negative signals ─────────────────────────────────────────────────────
    loyalty_vendors = list(profile.loyalty_vendors) if profile else []
    if loyalty_vendors:
        signals.append(
            Signal(
                "existing_loyalty",
                "Already runs a loyalty programme",
                ALREADY_LOYALTY_PENALTY,
                ", ".join(loyalty_vendors),
            )
        )

    # Floor at zero: a lead carrying the spam penalty could otherwise go
    # negative, and a negative score has no meaning the UI can render.
    total = max(0, min(SCORE_MAX, sum(s.points for s in signals)))
    return total, label_for(total), [s.as_dict() for s in signals]
