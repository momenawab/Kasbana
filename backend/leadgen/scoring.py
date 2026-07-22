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

**Traction-first, and that is a correction made against live data.** The spec's
table put 25 of its 100 points on web presence (website, email, social). Run
against 24 real Maadi cafes, only two had a website of their own — so 22 of 24
scored "Ignore", including Beano's Café at 4,384 reviews across two branches.
No rep would ever have opened that list.

The deeper error was not calibration but direction. A busy cafe with thousands
of reviews, no website and no loyalty programme is not a weak prospect for a
loyalty product — it is the *ideal* one: real footfall, no digital layer, and
nothing to displace. Scoring web presence as a pillar penalised exactly the
greenfield opportunity Stampn exists to serve. So the pillars are now traction
(reviews, rating), scale (branches) and reachability (a working phone), worth
76 between them; web presence is demoted to 16 points of convenience signal;
and an explicit greenfield signal rewards proven footfall with no incumbent
loyalty vendor.

The spec's phone weight is also split rather than placed entirely on "Verified
Phone": a valid, parseable number earns 8 and provider-confirmed reachability
earns 10. Under the original web-heavy weights this made Hot unreachable
without verification, which was a useful guard. It no longer holds, and
deliberately so: a business with thousands of reviews across several branches
is a hot lead whether or not a provider has confirmed its number, and pretending
otherwise would just re-introduce a threshold nobody in this market can clear.
Verification now adds confidence to a good lead rather than gating the label.
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


# ── Pillars: traction, scale, reachability (76 points) ───────────────────────
# Graduated rather than the spec's single ">500 reviews" cliff. At a cliff, 499
# reviews scores 0 and 500 scores 15, which is noise masquerading as judgement.
# Review volume is the closest observable proxy for footfall, and footfall is
# what a stamp-card business is worth — so it carries the most weight.
REVIEW_TIERS: tuple[tuple[int, int], ...] = ((1000, 25), (500, 20), (200, 14), (50, 8))
RATING_TIERS: tuple[tuple[float, int], ...] = ((4.5, 15), (4.2, 11), (4.0, 8), (3.5, 4))
# Branch count comes from the dedupe stage, which collapses a chain's listings
# into one lead. Multiple branches means budget, process, and a concrete reason
# to want cross-branch loyalty — one conversation worth several single sites.
BRANCH_TIERS: tuple[tuple[int, int], ...] = ((4, 18), (2, 12))

PHONE_VALID_POINTS = 8
PHONE_VERIFIED_POINTS = 10  # Phase 2 — awarded by the verification stage

# Proven footfall with no incumbent loyalty vendor: the easiest sale there is.
# Stated as its own signal rather than left implicit so the breakdown can say
# so in words, which is the line a rep can open with.
GREENFIELD_POINTS = 8
GREENFIELD_MIN_REVIEWS = 200

# ── Convenience signals (16 points) ──────────────────────────────────────────
# Useful for reaching a decision-maker, but not evidence of a good business.
# Two thirds of Egyptian F&B has no site at all; weighting these as pillars
# meant scoring most of the market as unsellable.
WEBSITE_POINTS = 4
EMAIL_POINTS = 4
INSTAGRAM_POINTS = 3
FACEBOOK_POINTS = 2
DIGITAL_PRESENCE_POINTS = 3  # already on a delivery/reservation platform

# ── Negatives ────────────────────────────────────────────────────────────────
# A business already running loyalty is not worthless — it has proven it wants
# the category — but it is a displacement sale, which is slower and cheaper.
# It also forfeits the greenfield signal, so the swing is larger than it looks.
ALREADY_LOYALTY_PENALTY = -15

# The spec's "-50 spam number" is deliberately not implemented. Spam-report
# counts come from crowd-sourced caller-ID databases with no lawful API, so we
# never learn them; a constant for a signal we cannot observe would be dead code
# implying a check that never runs. An unreachable number simply earns no
# reachability points, which is the honest expression of what we know.

# ── Labels ───────────────────────────────────────────────────────────────────
# Set against the observed distribution so all four buckets are populated by
# real businesses. Under these, Beano's (4,384 reviews, 2 branches, no site)
# reads Warm and reaches Hot once its phone is verified — which is the point:
# the best business in the area should not be labelled "Ignore".
HOT_MIN = 75
WARM_MIN = 55
COLD_MIN = 35


def label_for(score: int) -> str:
    if score >= HOT_MIN:
        return enums.ScoreLabel.HOT
    if score >= WARM_MIN:
        return enums.ScoreLabel.WARM
    if score >= COLD_MIN:
        return enums.ScoreLabel.COLD
    return enums.ScoreLabel.IGNORE


def _phone_detail(check) -> str:
    """What the breakdown says about reachability, including when unchecked."""
    if check is None:
        return "Not verified yet"
    if check.result == enums.VerificationResult.VERIFIED:
        parts = [check.get_line_type_display()] if check.line_type else []
        if check.carrier:
            parts.append(check.carrier)
        return " · ".join(parts) or "Confirmed by provider"
    if check.result == enums.VerificationResult.INVALID:
        return "Provider says this number is not valid"
    return "Looks valid, but reachability is unconfirmed"


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

    # Provider-confirmed reachability. Only a real lookup earns these points:
    # the offline fallback returns POSSIBLE precisely because it proves the
    # number *could* exist, not that anyone answers, and paying it the same
    # weight would make the signal mean nothing.
    phone_check = next(
        (
            check
            for check in lead.verifications.all()
            if check.kind == enums.VerificationKind.PHONE
        ),
        None,
    )
    verified = phone_check is not None and phone_check.result == enums.VerificationResult.VERIFIED
    signals.append(
        Signal(
            "phone_verified",
            "Phone confirmed reachable",
            PHONE_VERIFIED_POINTS if verified else 0,
            _phone_detail(phone_check),
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
    # ``socials`` and ``verifications`` are prefetched by ``pipeline.score``,
    # which reloads the lead specifically so this stays one query per lead
    # rather than three.
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

    # ── Greenfield ───────────────────────────────────────────────────────────
    # The thesis of the whole product: real footfall, no incumbent to displace.
    loyalty_vendors = list(profile.loyalty_vendors) if profile else []
    greenfield = lead.reviews_count >= GREENFIELD_MIN_REVIEWS and not loyalty_vendors
    signals.append(
        Signal(
            "greenfield",
            "Proven footfall, no loyalty programme yet",
            GREENFIELD_POINTS if greenfield else 0,
            f"{lead.reviews_count} reviews and no loyalty vendor detected"
            if greenfield
            else (
                ", ".join(loyalty_vendors)
                if loyalty_vendors
                else f"Only {lead.reviews_count} reviews — footfall unproven"
            ),
        )
    )

    # ── Negative signals ─────────────────────────────────────────────────────
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
