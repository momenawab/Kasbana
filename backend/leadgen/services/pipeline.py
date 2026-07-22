"""The enrichment stages a discovered business passes through.

Each stage is independently re-runnable and derives its output from scratch, so
retrying a failed job never double-counts and a lead can be re-enriched after a
bug fix without being re-discovered (and re-paid for).

Deduplication is a job-level pass rather than a per-lead check. Choosing which
listing survives requires seeing the whole group — the survivor should be the
best-documented branch, not whichever one Google happened to return first —
and that is only knowable once every cell has reported.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q

from leadgen import crawl as crawl_module
from leadgen import dedupe, enums, owner, scoring
from leadgen.models import GeneratedLead, SearchJob, SocialProfile, WebsiteProfile

logger = logging.getLogger(__name__)


# ── Stage 2: deduplication ───────────────────────────────────────────────────
def deduplicate(job: SearchJob) -> int:
    """Collapse duplicate listings within ``job``. Returns duplicates marked.

    Runs four passes in decreasing confidence — phone, then own domain, then
    same-location-and-similar-name. Place ID needs no pass: it is unique per job
    by constraint, so overlapping cells never create a second row for it.

    A chain's branches are absorbed rather than discarded: the survivor's
    ``branch_count`` becomes the number of listings that collapsed into it,
    which is exactly the "multiple branches" signal the score rewards.
    """
    leads = list(
        job.leads.filter(duplicate_of__isnull=True).order_by("-reviews_count", "created_at")
    )
    # place_id → the lead that will represent its group. Survivors are chosen by
    # review count (the best-documented listing of a chain is the one a rep
    # should call), which the ordering above already established.
    survivor_of: dict[str, GeneratedLead] = {}
    reason_of: dict[str, str] = {}

    by_phone: dict[str, GeneratedLead] = {}
    by_domain: dict[str, GeneratedLead] = {}
    named: list[GeneratedLead] = []

    for lead in leads:
        match, reason = None, ""

        if lead.phone_e164 and lead.phone_e164 in by_phone:
            match, reason = by_phone[lead.phone_e164], enums.DedupeReason.PHONE
        elif lead.website_domain and lead.website_domain in by_domain:
            match, reason = by_domain[lead.website_domain], enums.DedupeReason.WEBSITE
        else:
            match, reason = _name_match(lead, named)

        if match is not None:
            # Follow the chain: a duplicate of a duplicate belongs to the head.
            head = survivor_of.get(str(match.id), match)
            survivor_of[str(lead.id)] = head
            reason_of[str(lead.id)] = reason
            continue

        # First of its group — claim the keys.
        if lead.phone_e164:
            by_phone.setdefault(lead.phone_e164, lead)
        if lead.website_domain:
            by_domain.setdefault(lead.website_domain, lead)
        if lead.normalized_name:
            named.append(lead)

    return _persist_duplicates(job, leads, survivor_of, reason_of)


def _name_match(
    lead: GeneratedLead, named: list[GeneratedLead]
) -> tuple[GeneratedLead | None, str]:
    """A similarly-named business, either at the same address or elsewhere.

    Same coordinates plus a similar name is one listing duplicated. A similar
    name at a *different* address is a branch of the same chain, and both
    collapse — selling to a chain is one conversation with a head office.

    An empty normalised name (an all-filler business name) matches nothing:
    treating two empty strings as equal would merge unrelated businesses.
    """
    if not lead.normalized_name:
        return None, ""

    for candidate in named:
        if not candidate.normalized_name:
            continue
        if dedupe.name_similarity(lead.normalized_name, candidate.normalized_name) < (
            dedupe.NAME_MATCH_THRESHOLD
        ):
            continue

        if None not in (lead.lat, lead.lng, candidate.lat, candidate.lng):
            distance = dedupe.haversine_meters(
                lead.lat, lead.lng, candidate.lat, candidate.lng
            )
            reason = (
                enums.DedupeReason.COORDINATES
                if distance <= dedupe.SAME_LOCATION_METERS
                else enums.DedupeReason.SIMILAR_NAME
            )
        else:
            reason = enums.DedupeReason.SIMILAR_NAME

        return candidate, reason

    return None, ""


@transaction.atomic
def _persist_duplicates(
    job: SearchJob,
    leads: list[GeneratedLead],
    survivor_of: dict[str, GeneratedLead],
    reason_of: dict[str, str],
) -> int:
    if not survivor_of:
        return 0

    branch_counts: dict[str, int] = {}
    duplicates: list[GeneratedLead] = []

    for lead in leads:
        head = survivor_of.get(str(lead.id))
        if head is None:
            continue
        lead.duplicate_of = head
        lead.duplicate_reason = reason_of[str(lead.id)]
        lead.state = enums.LeadState.DUPLICATE
        duplicates.append(lead)
        branch_counts[str(head.id)] = branch_counts.get(str(head.id), 0) + 1

    GeneratedLead.objects.bulk_update(
        duplicates, ["duplicate_of", "duplicate_reason", "state"], batch_size=200
    )

    survivors = []
    for lead in leads:
        extra = branch_counts.get(str(lead.id))
        if extra:
            lead.branch_count = 1 + extra
            survivors.append(lead)
    GeneratedLead.objects.bulk_update(survivors, ["branch_count"], batch_size=200)

    job.duplicate_count = job.leads.filter(duplicate_of__isnull=False).count()
    job.save(update_fields=["duplicate_count", "updated_at"])
    return len(duplicates)


# ── Stage 3-4: website crawl + owner resolution ──────────────────────────────
def enrich(lead: GeneratedLead) -> None:
    """Crawl the lead's website and resolve an owner name. Never raises.

    A site being down, blocked or absent is ordinary — the lead keeps its Places
    signals and simply scores lower. Failing the lead here would discard a
    perfectly callable business because its web host had a bad minute.
    """
    lead.state = enums.LeadState.ENRICHING
    lead.save(update_fields=["state", "updated_at"])

    # A Places "website" that is really a social profile becomes the social row
    # it should have been — the single most common shape in Egyptian F&B, where
    # Instagram often *is* the entire web presence.
    if lead.website and not lead.website_domain:
        platform = dedupe.social_platform_for(lead.website)
        if platform:
            SocialProfile.objects.update_or_create(
                lead=lead, platform=platform, defaults={"url": lead.website}
            )

    result = None
    if lead.website_domain:
        result = crawl_module.WebsiteCrawler().crawl(lead.website)
        _store_website(lead, result)

    _store_owner(lead, result)


def _store_website(lead: GeneratedLead, result: crawl_module.CrawlResult) -> None:
    WebsiteProfile.objects.update_or_create(
        lead=lead,
        defaults={
            "fetched_at": None if result.error else _now(),
            "http_status": result.http_status,
            "error": result.error[:300],
            "pages_crawled": result.pages_crawled,
            "emails": result.emails,
            "phones": result.phones,
            "logo_url": result.logo_url,
            "meta_description": result.meta_description,
            "about_text": result.about_text,
            "legal_entity": result.legal_entity,
            "menu_urls": result.menu_urls,
            "reservation_platforms": result.reservation_platforms,
            "delivery_platforms": result.delivery_platforms,
            "technologies": result.technologies,
            "payment_providers": result.payment_providers,
            "pos_vendors": result.pos_vendors,
            "loyalty_vendors": result.loyalty_vendors,
        },
    )

    for platform, url in result.socials.items():
        SocialProfile.objects.update_or_create(
            lead=lead,
            platform=platform,
            defaults={"url": url[:500], "handle": _handle_from(url)},
        )


def _store_owner(lead: GeneratedLead, result: crawl_module.CrawlResult | None) -> None:
    """Record every owner candidate and promote the best one.

    Nothing is invented: with no candidates the lead keeps an empty owner name,
    which is the common outcome for small Egyptian businesses and is handled at
    import by setting a "identify decision-maker" next action. A rep opening a
    call with a guessed name is worse off than one opening with a question.

    Manually-entered candidates are never touched — a rep's own finding outranks
    anything automated, so re-running enrichment must not delete it.
    """
    lead.owner_candidates.exclude(source=enums.OwnerNameSource.MANUAL).delete()

    candidates: list[dict] = []
    if result is not None:
        candidates.extend(owner.extract_from_pages(result))
        candidates.extend(owner.extract_from_emails(result.emails, result.url))

    manual = list(lead.owner_candidates.filter(source=enums.OwnerNameSource.MANUAL))
    if not candidates and not manual:
        return

    for candidate in owner.deduplicate(candidates):
        lead.owner_candidates.create(
            name=candidate["name"],
            role=candidate["role"],
            source=candidate["source"],
            confidence=candidate["confidence"],
            evidence_url=candidate["evidence_url"],
            evidence_text=candidate["evidence_text"],
        )

    if manual:
        best = manual[0]
        lead.owner_name = best.name
        lead.owner_name_source = best.source
        lead.owner_name_confidence = best.confidence
    else:
        winner = owner.resolve(candidates)
        if winner:
            lead.owner_name = winner["name"]
            lead.owner_name_source = winner["source"]
            lead.owner_name_confidence = winner["confidence"]

    lead.save(
        update_fields=["owner_name", "owner_name_source", "owner_name_confidence", "updated_at"]
    )


def _handle_from(url: str) -> str:
    path = url.rstrip("/").rsplit("/", 1)[-1]
    return path[:160] if path and "." not in path else ""


def _now():
    from django.utils import timezone

    return timezone.now()


# ── Stage 5: scoring ─────────────────────────────────────────────────────────
def score(lead: GeneratedLead) -> int:
    """Recompute and persist the lead's fit score. Idempotent."""
    total, label, breakdown = scoring.score_lead(lead)
    lead.fit_score = total
    lead.score_label = label
    lead.score_breakdown = breakdown
    lead.save(update_fields=["fit_score", "score_label", "score_breakdown", "updated_at"])
    return total


# ── Stage 6: CRM duplicate check ─────────────────────────────────────────────
def match_crm(lead: GeneratedLead) -> bool:
    """Flag a pre-existing CRM lead for the same business. Returns whether matched.

    A match warns but never blocks: a shared phone across a food court, or a
    chain's head-office number on every branch, both produce legitimate matches
    that a rep should still be allowed to import and merge by hand.
    """
    from console.models import Lead as CrmLead

    query = Q(pk__isnull=True)  # never matches; the seed for an OR chain
    reason = ""

    if lead.phone_e164:
        query |= Q(phone=lead.phone_e164)
        reason = "phone"
    if lead.phone:
        query |= Q(phone=lead.phone)
        reason = reason or "phone"
    if lead.website_domain:
        query |= Q(website__icontains=lead.website_domain)
        reason = reason or "website"
    if lead.google_maps_url:
        query |= Q(google_maps_url=lead.google_maps_url)
        reason = reason or "google_maps_url"

    profile = getattr(lead, "website_profile", None)
    for email in (profile.emails if profile else [])[:3]:
        query |= Q(email__iexact=email)
        reason = reason or "email"

    match = CrmLead.objects.filter(query).order_by("created_at").first()
    if match is None:
        # Name-and-city is the last resort: it is the weakest signal, so it is
        # only consulted when nothing stronger matched.
        match = _match_by_name(lead)
        reason = "business_name" if match else ""

    lead.crm_match = match
    lead.crm_match_reason = reason if match else ""
    lead.state = enums.LeadState.DUPLICATE if match else enums.LeadState.READY
    lead.save(update_fields=["crm_match", "crm_match_reason", "state", "updated_at"])
    return match is not None


def _match_by_name(lead: GeneratedLead) -> object | None:
    from console.models import Lead as CrmLead

    if not lead.normalized_name:
        return None

    # Narrow on a shared first token before comparing — scanning the whole CRM
    # through the similarity function would be a table scan per lead.
    token = lead.normalized_name.split(" ")[0]
    if len(token) < 3:
        return None

    for candidate in CrmLead.objects.filter(business_name__icontains=token)[:50]:
        if (
            dedupe.name_similarity(
                lead.normalized_name, dedupe.normalize_name(candidate.business_name)
            )
            >= dedupe.NAME_MATCH_THRESHOLD
        ):
            return candidate
    return None
