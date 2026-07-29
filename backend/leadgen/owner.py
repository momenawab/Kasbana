"""Owner / decision-maker resolution from crawled pages.

Answers the question a rep actually needs before dialling: *who do I ask for?*

The design rule is that nothing is ever invented. Every candidate carries the
page it came from and the sentence that produced it, so a rep can check the
claim in one click. When no source fires — which is common for small Egyptian
cafes, many of which have no website at all — the lead imports with no owner
name and a next action of identifying the decision-maker. A thirty-second
question on the first call beats a confident guess that makes a rep open with
the wrong name.

A note on what "owner" means here. ``legal_entity`` from a privacy page is a
*company* ("Karam Group for Restaurants"), not a person, and the two must not
be conflated: addressing an email to "Dear Karam Group for Restaurants" is
worse than addressing it to nobody. Companies are returned separately, for the
CRM's company field.
"""

from __future__ import annotations

import re

from leadgen import enums
from leadgen.crawl import ROLE_EMAIL_PREFIXES, CrawlResult

# Roles that indicate the person who can sign. Ordered by decisiveness — a
# founder outranks a manager when both appear on the same page.
_OWNER_ROLES: tuple[tuple[str, int], ...] = (
    ("founder", 3),
    ("co-founder", 3),
    ("owner", 3),
    ("proprietor", 3),
    ("ceo", 3),
    ("chairman", 3),
    ("managing director", 3),
    ("md", 2),
    ("general manager", 2),
    ("gm", 2),
    ("director", 2),
    ("partner", 2),
    ("operations manager", 1),
    ("branch manager", 1),
    ("manager", 1),
    # Arabic
    ("المالك", 3),
    ("صاحب", 3),
    ("المؤسس", 3),
    ("مؤسس", 3),
    ("الرئيس التنفيذي", 3),
    ("المدير العام", 2),
    ("مدير", 1),
)

_ROLE_ALTERNATION = "|".join(re.escape(role) for role, _ in _OWNER_ROLES)

# "Ahmed Karam, Founder" / "Ahmed Karam - Owner"
_NAME_THEN_ROLE = re.compile(
    rf"([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){{1,3}})\s*[,\-–—|·]\s*({_ROLE_ALTERNATION})\b",
    re.IGNORECASE,
)
# "Founder: Ahmed Karam" / "Owner - Ahmed Karam"
_ROLE_THEN_NAME = re.compile(
    rf"\b({_ROLE_ALTERNATION})\s*[:\-–—|·]\s*([A-Z][\w'’\-]+(?:\s+[A-Z][\w'’\-]+){{1,3}})",
    re.IGNORECASE,
)
# Arabic: "المالك: أحمد كرم" — Arabic has no case, so the name is any run of
# Arabic words after the marker.
_ARABIC_ROLE_THEN_NAME = re.compile(
    rf"({_ROLE_ALTERNATION})\s*[:\-–—|·]?\s*((?:[ء-ي]+\s+){{1,3}}[ء-ي]+)"
)

# Strings that match the shape of a name but never are one. Without this, "Our
# Story" and "Privacy Policy" become candidate owners on almost every site.
_NAME_STOPWORDS: frozenset[str] = frozenset(
    {
        "our",
        "story",
        "about",
        "us",
        "privacy",
        "policy",
        "terms",
        "service",
        "conditions",
        "contact",
        "home",
        "menu",
        "all",
        "rights",
        "reserved",
        "copyright",
        "company",
        "group",
        "restaurant",
        "cafe",
        "coffee",
        "the",
        "team",
        "read",
        "more",
        "learn",
        "follow",
        "order",
        "now",
    }
)

# Confidence per source. A legal page names the operator under legal obligation;
# an email local part is a shape, not a statement.
_SOURCE_CONFIDENCE: dict[str, str] = {
    enums.OwnerNameSource.MANUAL: enums.Confidence.HIGH,
    enums.OwnerNameSource.LEGAL_PAGE: enums.Confidence.HIGH,
    enums.OwnerNameSource.ABOUT_PAGE: enums.Confidence.MEDIUM,
    enums.OwnerNameSource.FOOTER: enums.Confidence.MEDIUM,
    enums.OwnerNameSource.REVIEW_RESPONSE: enums.Confidence.MEDIUM,
    enums.OwnerNameSource.EMAIL_LOCAL_PART: enums.Confidence.LOW,
}

# Ranking order for picking the winner: source trust first, then how decisive
# the stated role is.
_SOURCE_RANK: dict[str, int] = {
    enums.OwnerNameSource.MANUAL: 0,
    enums.OwnerNameSource.LEGAL_PAGE: 1,
    enums.OwnerNameSource.ABOUT_PAGE: 2,
    enums.OwnerNameSource.REVIEW_RESPONSE: 3,
    enums.OwnerNameSource.FOOTER: 4,
    enums.OwnerNameSource.EMAIL_LOCAL_PART: 5,
}

_PAGE_KIND_TO_SOURCE: dict[str, str] = {
    "legal": enums.OwnerNameSource.LEGAL_PAGE,
    "about": enums.OwnerNameSource.ABOUT_PAGE,
    "contact": enums.OwnerNameSource.ABOUT_PAGE,
    "footer": enums.OwnerNameSource.FOOTER,
}


def _looks_like_a_name(value: str) -> bool:
    """Reject page furniture that happens to be capitalised like a name."""
    words = [w for w in re.split(r"\s+", value.strip()) if w]
    if not 2 <= len(words) <= 4:
        return False
    if any(word.lower() in _NAME_STOPWORDS for word in words):
        return False
    # A name is letters, apostrophes and hyphens — never digits or @.
    return all(re.fullmatch(r"[\w'’\-]+", word) and not word.isdigit() for word in words)


def _role_weight(role: str) -> int:
    lowered = role.lower().strip()
    for name, weight in _OWNER_ROLES:
        if name == lowered:
            return weight
    return 0


def _candidate(name: str, role: str, source: str, url: str, evidence: str) -> dict:
    return {
        "name": name.strip()[:160],
        "role": role.strip()[:120],
        "source": source,
        "confidence": _SOURCE_CONFIDENCE.get(source, enums.Confidence.LOW),
        "evidence_url": url[:500],
        "evidence_text": evidence.strip()[:500],
        # Not persisted — used only to order candidates before the winner is
        # chosen, so ranking stays a property of this module.
        "_rank": (_SOURCE_RANK.get(source, 9), -_role_weight(role)),
    }


def _snippet(text: str, match: re.Match) -> str:
    start = max(0, match.start() - 60)
    return text[start : match.end() + 60].replace("\n", " ")


def extract_from_pages(result: CrawlResult) -> list[dict]:
    """Owner candidates from the pages a crawl collected."""
    candidates: list[dict] = []

    for url, kind, text in result.owner_sources:
        source = _PAGE_KIND_TO_SOURCE.get(kind)
        if not source:
            continue

        for match in _NAME_THEN_ROLE.finditer(text):
            name, role = match.group(1), match.group(2)
            if _looks_like_a_name(name):
                candidates.append(_candidate(name, role, source, url, _snippet(text, match)))

        for match in _ROLE_THEN_NAME.finditer(text):
            role, name = match.group(1), match.group(2)
            if _looks_like_a_name(name):
                candidates.append(_candidate(name, role, source, url, _snippet(text, match)))

        for match in _ARABIC_ROLE_THEN_NAME.finditer(text):
            role, name = match.group(1), match.group(2)
            # Arabic names skip _looks_like_a_name: the pattern already
            # requires 2-4 Arabic words, and the Latin stopword list would
            # never apply.
            candidates.append(_candidate(name, role, source, url, _snippet(text, match)))

    return candidates


def extract_from_emails(emails: list[str], url: str = "") -> list[dict]:
    """Personal-looking email local parts, as a last resort.

    ``ahmed.karam@karam.com.eg`` suggests a person; ``info@`` names a
    department. Only the former is offered, at low confidence, because a local
    part is a shape and not a statement — it might be an employee, or a
    previous owner whose address was never retired.
    """
    candidates: list[dict] = []

    for email in emails:
        local = email.split("@", 1)[0].lower()
        if local in ROLE_EMAIL_PREFIXES or local.isdigit() or len(local) < 3:
            continue

        parts = [p for p in re.split(r"[._\-]+", local) if p.isalpha() and len(p) > 1]
        if len(parts) < 2:
            # A single token could be a first name, but could equally be
            # "bookings" or a brand. Not enough to put in front of a rep.
            continue

        name = " ".join(part.capitalize() for part in parts[:3])
        candidates.append(_candidate(name, "", enums.OwnerNameSource.EMAIL_LOCAL_PART, url, email))

    return candidates


def extract_from_review_responses(reviews: list[dict]) -> list[dict]:
    """Names signing an owner's reply to a Google review.

    Cheap and surprisingly effective for Egyptian F&B, where owners answer
    reviews personally and sign off ("شكراً — أحمد"). Only *owner* replies are
    read; a customer's review text is not a source.
    """
    candidates: list[dict] = []

    for review in reviews:
        text = (review.get("text") or "").strip()
        if not text:
            continue
        for pattern in (_NAME_THEN_ROLE, _ROLE_THEN_NAME, _ARABIC_ROLE_THEN_NAME):
            for match in pattern.finditer(text):
                groups = match.groups()
                name, role = (
                    (groups[0], groups[1]) if pattern is _NAME_THEN_ROLE else (groups[1], groups[0])
                )
                if pattern is _ARABIC_ROLE_THEN_NAME or _looks_like_a_name(name):
                    candidates.append(
                        _candidate(
                            name,
                            role,
                            enums.OwnerNameSource.REVIEW_RESPONSE,
                            review.get("url", ""),
                            text[:300],
                        )
                    )

    return candidates


def resolve(candidates: list[dict]) -> dict | None:
    """The candidate a rep should see first, or None when nothing fired.

    None is a legitimate, common answer and must be preserved as such — the
    caller records no owner name rather than promoting a weak guess.
    """
    if not candidates:
        return None
    return min(candidates, key=lambda c: c["_rank"])


def deduplicate(candidates: list[dict]) -> list[dict]:
    """Collapse the same person found on several pages, keeping the best source."""
    best: dict[str, dict] = {}
    for candidate in sorted(candidates, key=lambda c: c["_rank"]):
        key = candidate["name"].casefold()
        best.setdefault(key, candidate)
    return sorted(best.values(), key=lambda c: c["_rank"])


def company_name(result: CrawlResult) -> str:
    """The operating company, when a legal page named one.

    Kept separate from the owner: a company is not a person, and greeting a
    rep's email to "Karam Group for Restaurants" is worse than greeting nobody.
    """
    return result.legal_entity
