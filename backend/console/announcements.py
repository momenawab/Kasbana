"""Announcement send + stats helpers (Phase 10).

``send()`` is a plain function (the Celery task + the admin ``/send`` endpoint
both call it) so the delivery path is identical whether it fires now or from the
scheduler. Idempotent-ish: a SENT announcement is never re-sent, and in-app
delivery rows use ``ignore_conflicts`` so a partial retry can't duplicate them.
"""

from __future__ import annotations

from typing import Any

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from accounts.models import MerchantSettings
from console import segments
from console.merchants import owner_contact
from console.models import Announcement, AnnouncementDelivery


def audience_count(audience: str, param: str = "") -> int:
    """Preview: how many merchants a segment resolves to (no side effects)."""
    return segments.resolve(audience, param).count()


@transaction.atomic
def send(announcement: Announcement) -> dict[str, Any]:
    """Deliver ``announcement`` to its segment (in-app rows + emails). No-op if
    already SENT."""
    if announcement.status == Announcement.Status.SENT:
        return stats(announcement)

    merchants = list(segments.resolve(announcement.audience, announcement.audience_param))
    announcement.recipients = len(merchants)

    if announcement.channel in (Announcement.Channel.IN_APP, Announcement.Channel.BOTH):
        AnnouncementDelivery.objects.bulk_create(
            [AnnouncementDelivery(announcement=announcement, merchant=m) for m in merchants],
            ignore_conflicts=True,
        )

    if announcement.channel in (Announcement.Channel.EMAIL, Announcement.Channel.BOTH):
        # Broadcasts honour the merchant's "Email notifications" preference; the
        # in-app rows above do not (the toggle is email-only), and transactional
        # mail — password reset, billing dunning, support replies — never checks
        # it. Resolved in one query: a segment can be every merchant on the
        # platform. No settings row = opted in.
        opted_out = set(
            MerchantSettings.objects.filter(merchant__in=merchants, notif_email=False).values_list(
                "merchant_id", flat=True
            )
        )
        sent = 0
        for m in merchants:
            if m.id in opted_out:
                continue
            owner = owner_contact(m)
            if owner["email"]:
                send_mail(
                    subject=announcement.title,
                    message=announcement.body,
                    from_email=None,
                    recipient_list=[owner["email"]],
                    fail_silently=True,
                )
                sent += 1
        announcement.emails_sent = sent

    announcement.status = Announcement.Status.SENT
    announcement.sent_at = timezone.now()
    announcement.save()
    return stats(announcement)


def stats(announcement: Announcement) -> dict[str, Any]:
    """Delivery stats for an announcement."""
    delivered = announcement.deliveries.count()
    opened = announcement.deliveries.exclude(read_at__isnull=True).count()
    return {
        "recipients": announcement.recipients,
        "delivered": delivered,
        "emails_sent": announcement.emails_sent,
        "opened": opened,
        "open_rate": (opened / delivered) if delivered else 0.0,
    }
