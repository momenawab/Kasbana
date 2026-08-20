"""Website crawl — what a business publishes about itself.

Scope is deliberately narrow: the business's own domain, a handful of pages, no
JavaScript execution. Everything extracted here is material the business chose
to publish for customers to read, which is what makes it both reliable and
unproblematic to store.

What this does NOT do, and why:

* No social crawling. Instagram/Facebook/TikTok block it and forbid it, so a
  follower count would be null in production and would silently drag any score
  that trusted it. Social links found on the site are recorded as profiles; the
  platforms themselves are never fetched.
* No headless browser. It would roughly triple the cost of every crawl for the
  minority of sites that need it, and the fields we want — contact details,
  footer entity, social links, meta tags — are in the served HTML on nearly all
  small-business sites.
* No crawling of platform domains. A Places "website" is frequently an
  Instagram profile or a chain parent's site (see ``dedupe.is_own_domain``),
  and following those is both useless and rude.

robots.txt is honoured. A lead-generation crawler that ignores it is how a
server IP ends up on a blocklist, taking the rest of the platform with it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

from leadgen import dedupe

logger = logging.getLogger(__name__)

# Pages worth trying beyond the homepage, in priority order. The legal pages
# lead because they are the most reliable identity source on any site: privacy
# and terms pages are obliged to name the operating entity, and almost nobody
# thinks to look there.
CANDIDATE_PATHS: tuple[str, ...] = (
    "/privacy",
    "/privacy-policy",
    "/terms",
    "/terms-of-service",
    "/legal",
    "/about",
    "/about-us",
    "/our-story",
    "/team",
    "/contact",
    "/contact-us",
)

# Link text that marks a page worth following, in both languages. Matching on
# link text as well as path catches the many sites whose URLs are opaque
# (/page/12) but whose navigation is clear.
_LINK_HINTS: tuple[str, ...] = (
    "about",
    "about us",
    "our story",
    "team",
    "contact",
    "contact us",
    "privacy",
    "terms",
    "legal",
    "من نحن",
    "عن",
    "من نحن؟",
    "اتصل بنا",
    "تواصل معنا",
    "الخصوصية",
    "سياسة الخصوصية",
    "الشروط",
    "فريق",
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Loose on purpose — validation is ``dedupe.normalize_phone``'s job, and being
# strict here loses numbers written with unusual separators.
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-().]{7,}\d)")

# Addresses that are never a person to contact: no-reply boxes and the generic
# aliases every hosting package creates. Kept out of the lead's contact list so
# a rep never emails a black hole.
_JUNK_EMAIL_PREFIXES: tuple[str, ...] = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "postmaster",
    "abuse",
    "webmaster",
    "hostmaster",
    "mailer-daemon",
)
# Role addresses: real, but a department rather than a person. Kept — for a
# small cafe info@ is often the owner — but flagged so owner resolution does
# not mistake "info" for somebody's name.
ROLE_EMAIL_PREFIXES: frozenset[str] = frozenset(
    {
        "info",
        "contact",
        "hello",
        "sales",
        "support",
        "admin",
        "office",
        "reservations",
        "booking",
        "orders",
        "marketing",
        "hr",
        "careers",
        "jobs",
    }
)

# Asset filenames match the email pattern exactly: "logo@2x.png" parses as a
# local part, an @, and a "domain" of 2x.png. A generic TLD-length or
# is-alphabetic test does not catch it — "png" passes both — so the extension
# has to be named. Retina image suffixes appear on a large share of sites.
_ASSET_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".avif",
    ".ico",
    ".css",
    ".js",
    ".json",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".mp4",
    ".webm",
    ".zip",
)

# Vendor fingerprints. Detection is by the markup a vendor's embed leaves
# behind, so a match means the tool is actually installed rather than merely
# mentioned. MENA-specific vendors matter more here than the global ones —
# Foodics and Marn are what Egyptian F&B actually runs.
POS_SIGNATURES: dict[str, tuple[str, ...]] = {
    "foodics": ("foodics.com", "foodics.io"),
    "marn": ("marn.com", "marnpos"),
    "posrocket": ("posrocket.com",),
    "square": ("squareup.com", "square.site"),
    "toast": ("toasttab.com",),
    "lightspeed": ("lightspeedhq.com",),
}
LOYALTY_SIGNATURES: dict[str, tuple[str, ...]] = {
    "smiles": ("smiles.com",),
    "loyverse": ("loyverse.com",),
    "stampme": ("stampme.com",),
    "loopy": ("loopyloyalty.com",),
    "yotpo": ("yotpo.com", "swellrewards"),
    "smile.io": ("smile.io",),
}
PAYMENT_SIGNATURES: dict[str, tuple[str, ...]] = {
    "paymob": ("paymob.com", "accept.paymob"),
    "fawry": ("fawry.com", "atfawry"),
    "kashier": ("kashier.io",),
    "tap": ("tap.company", "gosell.io"),
    "stripe": ("js.stripe.com", "stripe.com/v3"),
    "paypal": ("paypal.com/sdk",),
    "checkout.com": ("checkout.com",),
}
DELIVERY_SIGNATURES: dict[str, tuple[str, ...]] = {
    "talabat": ("talabat.com",),
    "elmenus": ("elmenus.com",),
    "otlob": ("otlob.com",),
    "breadfast": ("breadfast.com",),
    "instashop": ("instashop.com",),
    "hungerstation": ("hungerstation.com",),
    "ubereats": ("ubereats.com",),
    "deliveroo": ("deliveroo.",),
}
RESERVATION_SIGNATURES: dict[str, tuple[str, ...]] = {
    "opentable": ("opentable.com",),
    "thefork": ("thefork.com", "lafourchette"),
    "resy": ("resy.com",),
    "sevenrooms": ("sevenrooms.com",),
    "quandoo": ("quandoo.com",),
}
TECH_SIGNATURES: dict[str, tuple[str, ...]] = {
    "wordpress": ("wp-content", "wp-includes"),
    "shopify": ("cdn.shopify.com", "shopify.com/s/"),
    "wix": ("wixstatic.com", "parastorage.com"),
    "squarespace": ("squarespace.com",),
    "webflow": ("webflow.com", "webflow.io"),
    "woocommerce": ("woocommerce",),
    "google_analytics": ("google-analytics.com", "gtag/js", "googletagmanager.com"),
    "meta_pixel": ("connect.facebook.net",),
}

_MENU_HINTS: tuple[str, ...] = ("menu", "our-menu", "food", "المنيو", "القائمة", "منيو")


@dataclass
class CrawlResult:
    """Everything one crawl found. Mirrors ``WebsiteProfile`` plus owner hints."""

    url: str
    http_status: int | None = None
    error: str = ""
    pages_crawled: int = 0

    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    socials: dict[str, str] = field(default_factory=dict)  # platform -> url

    logo_url: str = ""
    meta_description: str = ""
    about_text: str = ""
    legal_entity: str = ""

    menu_urls: list[str] = field(default_factory=list)
    reservation_platforms: list[str] = field(default_factory=list)
    delivery_platforms: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    payment_providers: list[str] = field(default_factory=list)
    pos_vendors: list[str] = field(default_factory=list)
    loyalty_vendors: list[str] = field(default_factory=list)

    # (page_url, page_kind, raw_text) for the owner-resolution cascade, which
    # needs to know *which* page a name came from to rank it.
    owner_sources: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return not self.error and self.pages_crawled > 0


def _page_kind(path: str) -> str:
    """Classify a path so owner resolution can weight what it finds there."""
    lowered = path.lower()
    if any(token in lowered for token in ("privacy", "terms", "legal")):
        return "legal"
    if any(token in lowered for token in ("about", "story", "team", "من-نحن")):
        return "about"
    if "contact" in lowered:
        return "contact"
    return "home"


class WebsiteCrawler:
    """Fetches a handful of pages from one business's own site.

    One instance per lead. Not reused across leads: it caches robots.txt for the
    host it was built for, and that cache would be wrong for the next one.
    """

    def __init__(
        self,
        *,
        timeout: float | None = None,
        max_pages: int | None = None,
        max_bytes: int | None = None,
        user_agent: str | None = None,
        respect_robots: bool = True,
    ):
        self.timeout = timeout or settings.LEADGEN_CRAWL_TIMEOUT
        self.max_pages = max_pages or settings.LEADGEN_CRAWL_MAX_PAGES
        self.max_bytes = max_bytes or settings.LEADGEN_CRAWL_MAX_BYTES
        self.user_agent = user_agent or settings.LEADGEN_CRAWL_USER_AGENT
        self.respect_robots = respect_robots
        self._robots: RobotFileParser | None = None

    # ── fetching ─────────────────────────────────────────────────────────────
    def _load_robots(self, client: httpx.Client, base: str) -> None:
        parser = RobotFileParser()
        try:
            response = client.get(urljoin(base, "/robots.txt"))
            # A site with no robots.txt permits everything; only a served file
            # constrains us. Treating a 404 as "disallow" would skip most
            # small-business sites, which rarely publish one.
            parser.parse(response.text.splitlines() if response.status_code == 200 else [])
        except httpx.HTTPError:
            parser.parse([])
        self._robots = parser

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots or self._robots is None:
            return True
        try:
            return self._robots.can_fetch(self.user_agent, url)
        except Exception:  # a malformed robots.txt must not fail the crawl
            return True

    def _fetch(self, client: httpx.Client, url: str) -> tuple[int | None, str]:
        """Return ``(status, html)``. Never raises — a failed page is skipped."""
        if not self._allowed(url):
            logger.info("crawl.robots_disallowed", extra={"url": url})
            return None, ""
        try:
            response = client.get(url)
        except httpx.HTTPError as exc:
            logger.info("crawl.fetch_failed", extra={"url": url, "error": str(exc)})
            return None, ""

        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return response.status_code, ""
        # Truncate rather than reject: an oversized page is usually a bloated
        # homepage, and its <head> and footer are still worth reading.
        return response.status_code, response.text[: self.max_bytes]

    # ── orchestration ────────────────────────────────────────────────────────
    def crawl(self, website: str) -> CrawlResult:
        """Crawl ``website`` and return what was found.

        Failure is reported, never raised: a site being down is ordinary and
        must not fail the lead, which still scores on its Places signals.
        """
        domain = dedupe.registrable_domain(website)
        result = CrawlResult(url=website)

        if not domain:
            result.error = "Not a usable website URL"
            return result
        if not dedupe.is_own_domain(domain):
            # Instagram profiles and chain parents reach here often. The caller
            # records the social link; there is nothing to crawl.
            result.error = f"{domain} is a platform, not the business's own site"
            return result

        base = website if website.startswith("http") else f"https://{website}"

        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                self._load_robots(client, base)

                status, html = self._fetch(client, base)
                result.http_status = status
                if not html:
                    result.error = f"Homepage returned no HTML (status {status})"
                    return result

                soup = BeautifulSoup(html, "lxml")
                result.pages_crawled = 1
                self._absorb(result, base, html, soup, "home")

                for url in self._next_pages(base, soup):
                    if result.pages_crawled >= self.max_pages:
                        break
                    _, page_html = self._fetch(client, url)
                    if not page_html:
                        continue
                    result.pages_crawled += 1
                    self._absorb(
                        result,
                        url,
                        page_html,
                        BeautifulSoup(page_html, "lxml"),
                        _page_kind(urlparse(url).path),
                    )
        except Exception as exc:  # noqa: BLE001 — one lead must not fail a job
            logger.warning("crawl.failed", extra={"url": website, "error": str(exc)})
            result.error = f"Crawl failed: {exc}"

        _dedupe_lists(result)
        return result

    def _next_pages(self, base: str, soup: BeautifulSoup) -> list[str]:
        """Same-host pages worth following, legal and about pages first."""
        host = urlparse(base).netloc
        found: dict[str, str] = {}

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = urljoin(base, href)
            if urlparse(absolute).netloc != host:
                continue

            path = urlparse(absolute).path.lower()
            text = anchor.get_text(" ", strip=True).lower()
            if any(p in path for p in CANDIDATE_PATHS) or any(h == text for h in _LINK_HINTS):
                found.setdefault(absolute.split("#")[0], _page_kind(path))

        # Legal first, then about, then contact — the order owner resolution
        # trusts, so the highest-value page is fetched even if the budget runs out.
        rank = {"legal": 0, "about": 1, "contact": 2, "home": 3}
        return sorted(found, key=lambda url: rank.get(found[url], 3))

    # ── extraction ───────────────────────────────────────────────────────────
    def _absorb(
        self, result: CrawlResult, url: str, html: str, soup: BeautifulSoup, kind: str
    ) -> None:
        lowered = html.lower()

        result.emails.extend(_extract_emails(soup, html))
        result.phones.extend(_PHONE_RE.findall(soup.get_text(" ", strip=True))[:20])

        for link in soup.find_all("a", href=True):
            platform = dedupe.social_platform_for(link["href"])
            if platform:
                result.socials.setdefault(platform, link["href"])

        if kind == "home":
            result.meta_description = _meta_description(soup)
            result.logo_url = _logo_url(soup, url)

        if kind == "about" and not result.about_text:
            result.about_text = soup.get_text(" ", strip=True)[:2000]

        for name, needles in TECH_SIGNATURES.items():
            if any(n in lowered for n in needles):
                result.technologies.append(name)
        for target, signatures in (
            (result.pos_vendors, POS_SIGNATURES),
            (result.loyalty_vendors, LOYALTY_SIGNATURES),
            (result.payment_providers, PAYMENT_SIGNATURES),
            (result.delivery_platforms, DELIVERY_SIGNATURES),
            (result.reservation_platforms, RESERVATION_SIGNATURES),
        ):
            for name, needles in signatures.items():
                if any(n in lowered for n in needles):
                    target.append(name)

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(" ", strip=True).lower()
            if any(h in href.lower() or h == text for h in _MENU_HINTS):
                result.menu_urls.append(urljoin(url, href))

        if kind == "legal" and not result.legal_entity:
            result.legal_entity = _legal_entity(soup.get_text(" ", strip=True))

        # Footer text from every page: the copyright line is the cheapest
        # entity signal there is, and it is not always on the homepage.
        footer = soup.find("footer")
        if footer:
            result.owner_sources.append((url, "footer", footer.get_text(" ", strip=True)[:1000]))
        if kind in ("legal", "about", "contact"):
            result.owner_sources.append((url, kind, soup.get_text(" ", strip=True)[:4000]))


def _extract_emails(soup: BeautifulSoup, html: str) -> list[str]:
    """Emails from mailto links and body text, minus the no-reply boxes."""
    found = {
        link["href"].split("mailto:", 1)[-1].split("?")[0].strip().lower()
        for link in soup.find_all("a", href=True)
        if link["href"].lower().startswith("mailto:")
    }
    found.update(match.lower() for match in _EMAIL_RE.findall(html))

    return [
        email
        for email in sorted(found)
        if "@" in email
        and not email.split("@")[0].startswith(_JUNK_EMAIL_PREFIXES)
        and not email.endswith(_ASSET_EXTENSIONS)
        and len(email.rsplit(".", 1)[-1]) >= 2
        and email.rsplit(".", 1)[-1].isalpha()
    ]


def _meta_description(soup: BeautifulSoup) -> str:
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"].strip()[:500]
    return ""


def _logo_url(soup: BeautifulSoup, base: str) -> str:
    """Best-guess logo: og:image, then an <img> whose markup says "logo"."""
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return urljoin(base, og["content"])
    for img in soup.find_all("img", src=True):
        haystack = f"{img.get('class', '')} {img.get('id', '')} {img.get('alt', '')} {img['src']}"
        if "logo" in haystack.lower():
            return urljoin(base, img["src"])
    return ""


# "© 2026 Karam Group for Restaurants", "All rights reserved to Karam Group",
# and the Arabic equivalents.
_ENTITY_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"(?:operated|owned|managed)\s+by\s+([^.,|·\n]{3,80})", re.I),
    re.compile(r"©\s*(?:\d{4}\s*[-–]?\s*\d{0,4}\s*)?([^.,|·\n]{3,80})"),
    re.compile(r"all\s+rights\s+reserved\s*(?:to|by)?\s*([^.,|·\n]{3,80})", re.I),
    re.compile(r"جميع\s+الحقوق\s+محفوظة\s*(?:لـ|ل)?\s*([^.,|·\n]{3,80})"),
)

# Page furniture that a run-on capture drags in. Seen live on zazacuisine.com,
# where the © capture returned "Privacy Policy Developed By Shoman Systems Item
# was added successfully Continu" — 80 characters of navigation text, because
# stripped page copy often contains no sentence punctuation at all to stop at.
#
# "developed/designed/powered by" is called out separately: those name the web
# agency, and an agency is emphatically not the business we are selling to.
_ENTITY_NOISE: tuple[str, ...] = (
    "privacy",
    "policy",
    "terms",
    "conditions",
    "cookie",
    "developed by",
    "designed by",
    "powered by",
    "item was",
    "successfully",
    "all rights",
    "reserved",
    "sign in",
    "log in",
    "add to cart",
    "read more",
    "menu",
)

# A company name is a handful of words. Beyond this the capture has plainly run
# into surrounding page text rather than found an entity.
_ENTITY_MAX_WORDS = 8


def _legal_entity(text: str) -> str:
    """The operating company named on a legal or footer line, or "".

    Returning "" is much better than returning noise: this value flows into the
    CRM's company field, where a rep reads it as fact.
    """
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            entity = match.group(1).strip(" -–—|·\t")
            if _plausible_entity(entity):
                return entity[:255]
    return ""


def _plausible_entity(entity: str) -> bool:
    if not entity or len(entity) < 3:
        return False
    lowered = entity.lower()
    if any(noise in lowered for noise in _ENTITY_NOISE):
        return False
    words = entity.split()
    if not 1 <= len(words) <= _ENTITY_MAX_WORDS:
        return False
    # Must read as a name, not a URL, an address or a slogan fragment.
    return any(char.isalpha() for char in entity) and "://" not in entity


def _dedupe_lists(result: CrawlResult) -> None:
    """Collapse repeats picked up across pages, preserving first-seen order."""
    for attribute in (
        "emails",
        "phones",
        "menu_urls",
        "reservation_platforms",
        "delivery_platforms",
        "technologies",
        "payment_providers",
        "pos_vendors",
        "loyalty_vendors",
    ):
        seen: dict[str, None] = {}
        for item in getattr(result, attribute):
            seen.setdefault(item, None)
        setattr(result, attribute, list(seen))
