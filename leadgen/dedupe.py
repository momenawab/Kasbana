"""Canonicalisation and duplicate detection for discovered businesses.

Pure functions plus one query-driven pass, kept apart from the Celery stage that
calls them so the rules are testable without a job, a broker, or a fixture.

The hard part is not the comparison, it is agreeing what two strings *are*
before comparing them. Places returns the same Cairo cafe as "Karam Café",
"كرم كافيه" and "KARAM CAFE - Maadi" depending on who created the listing, and
none of those match each other as bytes.

On chains: a chain's branches collapse into one lead on purpose. Selling Stampn
to Cilantro is one conversation with one head office, not fifty conversations
with fifty baristas, so the branches become ``branch_count`` on the survivor —
which is also exactly the "multiple branches" signal the score wants.
"""

from __future__ import annotations

import math
import re
import unicodedata
from difflib import SequenceMatcher

import phonenumbers
import tldextract
from phonenumbers import NumberParseException

# tldextract fetches the Public Suffix List over the network on first use. A
# Celery worker must not make an uncontrolled outbound call at import time (and
# would fail closed in a locked-down network), so we pin it to the snapshot
# bundled with the installed package. Refreshing the PSL is a dependency bump,
# which is the reviewable path.
_extract = tldextract.TLDExtract(suffix_list_urls=())

# ── Arabic normalisation ─────────────────────────────────────────────────────
# Without this, "مطعم كرم" and "مطعم كرم" (identical to a reader, different
# codepoints — one has a hamza on the alef) are two businesses. Egyptian
# listings are written by hand on phone keyboards, so these variants are the
# norm rather than the exception.
_ARABIC_DIACRITICS = re.compile(r"[ً-ٰٟـ]")
_ARABIC_FOLD = str.maketrans(
    {
        # Alef forms — the single most common inconsistency.
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        # Alef maqsura → ya, and ta marbuta → ha: both are spelling choices
        # rather than distinctions, and listings use them interchangeably.
        "ى": "ي",
        "ة": "ه",
        # Hamza carriers.
        "ؤ": "و",
        "ئ": "ي",
        "ء": "",
    }
)
# Arabic-Indic and Eastern Arabic-Indic digits. Phone numbers and branch names
# ("فرع ٢") arrive in both, and "٢" must equal "2" for dedupe to work.
_DIGIT_FOLD = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_NON_ALNUM = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

# Filler that carries no identity at all. Deliberately *not* a list of business
# types: "cafe", "kitchen" and "grill" look generic but genuinely distinguish
# ("Cairo Kitchen" and "Cairo Grill" are two businesses, and merging them would
# lose a real lead). Only words that no one would use to tell two businesses
# apart belong here.
_FILLER_TOKENS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "for",
        "of",
        "co",
        "company",
        "group",
        "est",
        "llc",
        "ltd",
        "inc",
        "شركه",
        "مجموعه",
    }
)

# Branch qualifiers: a location appended to a chain's name. Stripped so a
# chain's listings collapse onto one lead — "Karam Cafe Maadi" and "Karam Cafe
# Zamalek" are one sales conversation with one head office.
#
# Neighbourhoods only, never governorates or cities. "Cairo" and "Alexandria"
# are frequently the *brand* ("Cairo Kitchen"), so stripping them would erase
# the distinguishing token; neighbourhood names almost never are.
_BRANCH_TOKENS: frozenset[str] = frozenset(
    {
        "branch",
        "فرع",
        # Greater Cairo
        "maadi",
        "zamalek",
        "heliopolis",
        "mohandessin",
        "mohandiseen",
        "dokki",
        "nasr",
        "tagamoa",
        "tagamou",
        "rehab",
        "madinaty",
        "korba",
        "downtown",
        "obour",
        "shorouk",
        "zayed",
        "october",
        "6th",
        "sheraton",
        "manial",
        # Alexandria
        "smouha",
        "gleem",
        "stanley",
        "sidi",
        "bishr",
        "roushdy",
        # Arabic forms, post-fold (ta marbuta → ha, alef forms already folded)
        "المعادي",
        "معادي",
        "الزمالك",
        "زمالك",
        "مصر",
        "الجديده",
        "المهندسين",
        "مهندسين",
        "الدقي",
        "دقي",
        "نصر",
        "التجمع",
        "تجمع",
        "الرحاب",
        "زايد",
        "اكتوبر",
        "سموحه",
        "ستانلي",
    }
)

_STRIPPED_TOKENS = _FILLER_TOKENS | _BRANCH_TOKENS

# Two tokens this similar are the same word with a typo or a transliteration
# wobble ("karam"/"karm"). Below it they are different words.
_TOKEN_MATCH_THRESHOLD = 0.85


def normalize_name(name: str) -> str:
    """Canonical form of a business name for equality and similarity checks.

    Token-sorted, so word order stops mattering: "Cafe Karam" and "Karam Cafe"
    normalise identically. That is safe here because business names are short
    and their word order carries no meaning that distinguishes one business
    from another.

    Returns "" for a name that is entirely generic ("Restaurant"), which the
    caller must treat as *unmatchable* rather than as matching every other
    empty result.
    """
    if not name:
        return ""

    text = name.translate(_DIGIT_FOLD)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_FOLD)
    # NFKD splits Latin accents into base + combining mark; dropping the marks
    # folds "Café" onto "Cafe". Arabic is already handled above, and its marks
    # were stripped before this point.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _NON_ALNUM.sub(" ", text.casefold())
    text = _WHITESPACE.sub(" ", text).strip()

    tokens = [t for t in text.split(" ") if t and t not in _STRIPPED_TOKENS]
    return " ".join(sorted(tokens))


def name_similarity(left: str, right: str) -> float:
    """Similarity of two *already normalised* names, 0.0–1.0.

    Token-set based, not whole-string. Comparing the strings directly scores
    "karam maadi" against "karam zamalek" at 0.67 — the differing branch suffix
    dominates a character-level ratio even though the names share their entire
    identity. Matching token-by-token measures the thing that actually decides
    the question: how much of each name the other one accounts for.

    Tokens are paired greedily with a fuzzy comparison, so a transliteration
    wobble ("karam"/"karm") still pairs, and the result is the harmonic-style
    ratio ``2·matched / (len(a) + len(b))`` — which stays low when one name
    carries extra distinguishing words rather than rewarding mere overlap.

    ``SequenceMatcher`` from the stdlib rather than a fuzzy-matching dependency:
    comparisons are blocked by geography before they reach here, so this runs
    over tens of pairs per lead, not millions.
    """
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_tokens = left.split(" ")
    right_tokens = list(right.split(" "))

    matched = 0
    for token in left_tokens:
        best_index, best_ratio = -1, 0.0
        for index, candidate in enumerate(right_tokens):
            ratio = 1.0 if token == candidate else SequenceMatcher(None, token, candidate).ratio()
            if ratio > best_ratio:
                best_index, best_ratio = index, ratio
        if best_ratio >= _TOKEN_MATCH_THRESHOLD:
            matched += 1
            # Consumed, so two tokens on the left cannot both claim one on the
            # right and inflate the score above what the names share.
            right_tokens.pop(best_index)

    return 2 * matched / (len(left_tokens) + len(right.split(" ")))


def normalize_phone(raw: str, region: str) -> str:
    """E.164 form of ``raw``, or "" when it is not a valid number in ``region``.

    Invalid returns empty rather than raising: a malformed phone on a Places
    listing is ordinary, and it must not fail the lead. The unparsed original
    stays on ``GeneratedLead.phone`` so a rep can still read it.
    """
    if not raw:
        return ""
    try:
        parsed = phonenumbers.parse(raw.translate(_DIGIT_FOLD), region.upper() or None)
    except NumberParseException:
        return ""
    if not phonenumbers.is_valid_number(parsed):
        return ""
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def registrable_domain(url: str) -> str:
    """Registrable domain of ``url`` ("https://www.Karam.com.eg/menu" → "karam.com.eg").

    Public-suffix aware, which is the whole point: ".com.eg" is a suffix, so a
    naive two-label split would return "com.eg" for most Egyptian businesses and
    merge the entire result set into a single duplicate.
    """
    if not url:
        return ""
    parts = _extract(url.strip().lower())
    if not parts.domain or not parts.suffix:
        return ""
    return f"{parts.domain}.{parts.suffix}"


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two coordinates."""
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


# Domains that are somebody else's platform, not the business's own site.
#
# Found the hard way, on the first live Maadi search: one cafe's Places
# "website" was an Instagram profile, another's was ihg.com — the parent hotel
# chain. Both break things silently. Treating them as the business's website
# would (a) point the crawler at hosts that block it and forbid crawling, and
# (b) make the domain dedupe key merge every unrelated business sharing a
# platform into a single lead. A shared platform domain is evidence of nothing.
_PLATFORM_DOMAINS: frozenset[str] = frozenset(
    {
        # Social — usually the real presence for small Egyptian F&B, but a
        # social profile is a SocialProfile row, never a website.
        "instagram.com",
        "facebook.com",
        "fb.com",
        "fb.me",
        "tiktok.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "youtube.com",
        "wa.me",
        "whatsapp.com",
        "t.me",
        "telegram.me",
        "snapchat.com",
        "threads.net",
        # Link aggregators
        "linktr.ee",
        "linkin.bio",
        "beacons.ai",
        "carrd.co",
        "milkshake.app",
        # Delivery / listing marketplaces
        "talabat.com",
        "elmenus.com",
        "otlob.com",
        "hungerstation.com",
        "ubereats.com",
        "deliveroo.com",
        "glovoapp.com",
        "instashop.com",
        "zomato.com",
        "tripadvisor.com",
        "yelp.com",
        "foursquare.com",
        # Booking / hospitality parents
        "booking.com",
        "airbnb.com",
        "opentable.com",
        "thefork.com",
        "ihg.com",
        "marriott.com",
        "hilton.com",
        "accor.com",
        "hyatt.com",
        # Generic site builders' shared domains (a business on its own custom
        # domain is unaffected; only the shared host is excluded).
        "wixsite.com",
        "business.site",
        "godaddysites.com",
        "weebly.com",
        "blogspot.com",
        "wordpress.com",
        "square.site",
        "shopify.com",
        "google.com",
        "sites.google.com",
    }
)


def is_own_domain(domain: str) -> bool:
    """Whether ``domain`` is plausibly the business's own site.

    False for social profiles, marketplaces, aggregators and chain-parent sites
    — the places a Places "website" field routinely points instead of at the
    business. Callers use this for two decisions that must agree: whether to
    crawl it, and whether it may act as a dedupe key.
    """
    return bool(domain) and domain not in _PLATFORM_DOMAINS


# Which platform a URL belongs to, for turning a Places "website" that is really
# a social profile into the SocialProfile row it should have been.
_SOCIAL_DOMAINS: dict[str, str] = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "fb.me": "facebook",
    "tiktok.com": "tiktok",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "twitter.com": "x",
    "x.com": "x",
    "wa.me": "whatsapp",
    "whatsapp.com": "whatsapp",
}


def social_platform_for(url: str) -> str:
    """The ``SocialPlatform`` value ``url`` belongs to, or "" if it is not social."""
    return _SOCIAL_DOMAINS.get(registrable_domain(url), "")


# Two listings within this radius are at the same address for our purposes.
# Places coordinates for a single business vary by a few tens of metres between
# listings; 60m keeps a food court's separate units apart while still merging
# duplicate pins on one storefront.
SAME_LOCATION_METERS = 60.0

# Above this, two normalised names are the same business. Tuned on the failure
# that matters: below ~0.85, "Karam Cafe Maadi" starts matching "Karam Cafe
# Zamalek" — which we *do* want merged as branches — while genuinely different
# neighbours like "Beano's" and "Bean Bar" stay apart.
NAME_MATCH_THRESHOLD = 0.86
