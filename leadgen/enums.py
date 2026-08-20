"""Lead-generation vocabulary.

Kept separate from ``console.crm`` on purpose. That module owns the *sales
pipeline's* language — a lead's status, temperature and priority as a rep
works it. This module owns the *prospecting* language, which describes a
business we have not spoken to yet. The two never mix: a discovered business
has no temperature, and a working lead has no crawl status.

The one word that appears in both is "score", and it means different things —
see ``leadgen.scoring`` for why the fit score is stored here rather than on
``console.models.Lead``.
"""

from __future__ import annotations

from django.db import models


class JobStatus(models.TextChoices):
    """Lifecycle of one search job.

    ``PAUSED`` and ``CANCELLED`` are distinct because they differ in what
    happens to work already queued: a paused job's stages stop claiming new
    leads but keep their partial results, while a cancelled job is terminal and
    its pending stages are abandoned. Only ``PAUSED`` can return to ``RUNNING``.
    """

    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


# A job in one of these has finished for good; the UI stops polling it and
# ``retry`` re-enqueues from scratch rather than resuming.
TERMINAL_JOB_STATUSES: frozenset[str] = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)


class JobPriority(models.TextChoices):
    """Which Celery queue the job's stages run on.

    Not a sort order — a real routing decision. ``BACKGROUND`` exists so a
    1,000-result sweep cannot starve the interactive jobs a rep is watching.
    """

    HIGH = "high", "High"
    NORMAL = "normal", "Normal"
    BACKGROUND = "background", "Background"


class PipelineStage(models.TextChoices):
    """The ordered stages a discovered business passes through.

    Stored on both the job (where it is now) and the log (what emitted the
    line), so a stalled job says *which* stage stalled without a join.
    """

    DISCOVERY = "discovery", "Places Discovery"
    DEDUPLICATION = "deduplication", "Deduplication"
    WEBSITE_CRAWL = "website_crawl", "Website Crawl"
    OWNER_RESOLUTION = "owner_resolution", "Owner Resolution"
    SCORING = "scoring", "Scoring"
    CRM_MATCH = "crm_match", "CRM Duplicate Check"


class LeadState(models.TextChoices):
    """Where a discovered business sits in *our* funnel, before sales sees it.

    Deliberately not ``console.crm.LeadStatus``: these describe enrichment
    progress, not a sales conversation. A lead leaves this vocabulary entirely
    once it is imported, at which point the CRM's status takes over.
    """

    DISCOVERED = "discovered", "Discovered"
    ENRICHING = "enriching", "Enriching"
    READY = "ready", "Ready for CRM"
    IMPORTED = "imported", "Imported"
    DUPLICATE = "duplicate", "Duplicate"
    REJECTED = "rejected", "Rejected"
    FAILED = "failed", "Failed"


class ScoreLabel(models.TextChoices):
    """Bucketed fit score. Thresholds live in ``leadgen.scoring``."""

    HOT = "hot", "Hot"
    WARM = "warm", "Warm"
    COLD = "cold", "Cold"
    IGNORE = "ignore", "Ignore"


class BusinessType(models.TextChoices):
    """What we search for. Mapped to Google Places types in ``leadgen.places``.

    These are *our* categories, not Google's, because several of them (dessert,
    pizza) are a Places ``type`` plus a keyword rather than a type on their own,
    and because the label a rep picks should not change when Google renames a
    type. The mapping is one-way and lives with the client that needs it.
    """

    CAFE = "cafe", "Cafe"
    COFFEE_SHOP = "coffee_shop", "Coffee Shop"
    RESTAURANT = "restaurant", "Restaurant"
    BAKERY = "bakery", "Bakery"
    DESSERT = "dessert", "Dessert"
    PIZZA = "pizza", "Pizza"
    FAST_FOOD = "fast_food", "Fast Food"
    GYM = "gym", "Gym"
    SALON = "salon", "Salon"
    RETAIL = "retail", "Retail"
    HOTEL = "hotel", "Hotel"
    HOSPITAL = "hospital", "Hospital"


# The spec fixes these; a free-text max would let one job exhaust a day of
# Places quota. Enforced in the serializer, restated here as the source of truth.
ALLOWED_MAX_RESULTS: tuple[int, ...] = (25, 50, 100, 250, 500, 1000)


class SocialPlatform(models.TextChoices):
    """Platforms we detect. Detection only — see ``leadgen.crawl``.

    We record that a business has an Instagram presence and its handle, both
    read from links the business publishes on its own site. We do not fetch
    follower counts or activity: those require crawling Meta/TikTok, which they
    block and forbid, so a field for them would be null in production and would
    quietly drag every score that trusted it.
    """

    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    TIKTOK = "tiktok", "TikTok"
    LINKEDIN = "linkedin", "LinkedIn"
    WHATSAPP = "whatsapp", "WhatsApp"
    YOUTUBE = "youtube", "YouTube"
    X = "x", "X"


class OwnerNameSource(models.TextChoices):
    """Where an owner-name candidate came from.

    Stored per candidate rather than collapsed into one field because a rep
    opening a call needs to know whether the name came from a legal document or
    from someone's guess. ``MANUAL`` is what a rep typed after finding it by
    means of their own; it outranks everything automated by definition.
    """

    MANUAL = "manual", "Entered by rep"
    LEGAL_PAGE = "legal_page", "Privacy policy / terms"
    ABOUT_PAGE = "about_page", "About / team page"
    FOOTER = "footer", "Website footer"
    REVIEW_RESPONSE = "review_response", "Signed Google review response"
    EMAIL_LOCAL_PART = "email_local_part", "Published email address"


class Confidence(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class LogLevel(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    ERROR = "error", "Error"


class TaskStatus(models.TextChoices):
    """Lifecycle of one queued unit of paid work — an AI call or a verification.

    Shared by both queues because the operator's question is the same for each:
    is it waiting, working, done, or stuck. ``SKIPPED`` is distinct from
    ``FAILED``: a lead with no email was never going to be verifiable, and
    counting that as a failure would make the queue look broken.
    """

    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class VerificationKind(models.TextChoices):
    PHONE = "phone", "Phone"
    EMAIL = "email", "Email"


class PhoneLineType(models.TextChoices):
    """What kind of line a number is, from a lookup provider.

    The useful signal for prospecting: a mobile reaches a person, a landline
    reaches a counter, and a VoIP number on a small F&B business is usually a
    reseller or a dead listing.
    """

    MOBILE = "mobile", "Mobile"
    LANDLINE = "landline", "Landline"
    VOIP = "voip", "VoIP"
    UNKNOWN = "unknown", "Unknown"


class VerificationResult(models.TextChoices):
    """The spec's four states, applied to both phones and emails."""

    VERIFIED = "verified", "Verified"
    POSSIBLE = "possible", "Possible"
    INVALID = "invalid", "Invalid"
    UNKNOWN = "unknown", "Unknown"


class ApiProvider(models.TextChoices):
    """Every paid third party the module can call.

    Names the *provider*, not the key: credentials stay in the environment
    alongside Paymob and WhatsApp (see ``leadgen.services.apikeys``). This
    enum exists so usage and cost can be attributed per provider.
    """

    GOOGLE_PLACES = "google_places", "Google Places"
    GOOGLE_GEOCODING = "google_geocoding", "Google Geocoding"
    GLM = "glm", "Zhipu GLM"
    TWILIO_LOOKUP = "twilio_lookup", "Twilio Lookup"
    HUNTER = "hunter", "Hunter.io"


class RiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"


class DedupeReason(models.TextChoices):
    """Why a discovered business was dropped or flagged as a duplicate.

    Recorded rather than inferred so a rep questioning a missing business gets
    an answer, and so tuning the name-similarity threshold is evidence-based.
    """

    PLACE_ID = "place_id", "Same Google Place ID"
    PHONE = "phone", "Same phone number"
    WEBSITE = "website", "Same website domain"
    COORDINATES = "coordinates", "Same coordinates"
    SIMILAR_NAME = "similar_name", "Similar name at same location"
