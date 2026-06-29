"""Apple Wallet web service — the 5 endpoints + initial download (contract §3.6).

Apple's external spec: camelCase fields, Apple's own status codes, no Stampn
error envelope. Implemented as plain Django views to control the raw responses.
Mounted under /api/v1/wallet/apple/.
"""

from __future__ import annotations

import json
import logging

from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core.enums import WalletPlatform
from core.models import CustomerCard, WalletRegistration
from wallets.apple.config import is_configured
from wallets.apple.signing import AppleSigningError, build_pkpass
from wallets.apple_webservice.auth import authenticate_pass

logger = logging.getLogger(__name__)


def _epoch(dt) -> int:
    return int(dt.timestamp())


@csrf_exempt
def register_device(request, device_library_id, pass_type_id, serial):
    """POST register · DELETE unregister a device for a pass (auth required)."""
    if request.method not in ("POST", "DELETE"):
        return HttpResponseNotAllowed(["POST", "DELETE"])

    cc = authenticate_pass(request, serial)
    if cc is None:
        return HttpResponse(status=401)

    if request.method == "DELETE":
        WalletRegistration.objects.filter(
            customer_card=cc,
            platform=WalletPlatform.APPLE,
            device_library_id=device_library_id,
        ).update(is_active=False)
        return HttpResponse(status=200)

    # POST: register (or re-activate) the device.
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    push_token = body.get("pushToken", "")

    reg, created = WalletRegistration.objects.get_or_create(
        customer_card=cc,
        platform=WalletPlatform.APPLE,
        device_library_id=device_library_id,
        defaults={"push_token": push_token, "is_active": True},
    )
    if not created:
        reg.push_token = push_token or reg.push_token
        reg.is_active = True
        reg.save(update_fields=["push_token", "is_active", "updated_at"])
    return HttpResponse(status=201 if created else 200)


@csrf_exempt
def list_updated_serials(request, device_library_id, pass_type_id):
    """GET serials registered to a device, updated since ?passesUpdatedSince."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    regs = WalletRegistration.objects.filter(
        platform=WalletPlatform.APPLE,
        device_library_id=device_library_id,
        is_active=True,
    ).select_related("customer_card")

    since = request.GET.get("passesUpdatedSince")
    serials: list[str] = []
    last_updated = 0
    for reg in regs:
        updated = _epoch(reg.customer_card.updated_at)
        if since is not None and updated <= int(since):
            continue
        serials.append(str(reg.customer_card_id))
        last_updated = max(last_updated, updated)

    if not serials:
        return HttpResponse(status=204)
    return JsonResponse({"serialNumbers": serials, "lastUpdated": str(last_updated)})


@csrf_exempt
def get_pass(request, pass_type_id, serial):
    """GET the latest .pkpass for a serial (auth required)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    cc = authenticate_pass(request, serial)
    if cc is None:
        return HttpResponse(status=401)

    # If-Modified-Since support: 304 when the pass hasn't changed.
    ims = request.META.get("HTTP_IF_MODIFIED_SINCE")
    if ims:
        try:
            from email.utils import parsedate_to_datetime

            if cc.updated_at <= parsedate_to_datetime(ims):
                return HttpResponse(status=304)
        except (TypeError, ValueError):
            pass

    try:
        pkpass = build_pkpass(cc)
    except AppleSigningError:
        return HttpResponse(status=503)

    resp = HttpResponse(pkpass, content_type="application/vnd.apple.pkpass")
    resp["Last-Modified"] = timezone.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    return resp


@csrf_exempt
def log(request):
    """POST device logs sink."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        body = json.loads(request.body or b"{}")
        for line in body.get("logs", []):
            logger.info("ApplePass device log: %s", line)
    except json.JSONDecodeError:
        pass
    return HttpResponse(status=200)


@csrf_exempt
def download_pass(request, customer_card_id):
    """Initial .pkpass download for the enrollment page (capability = UUID)."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    if not is_configured():
        return HttpResponse(status=503)
    cc = CustomerCard.objects.filter(id=customer_card_id).first()
    if cc is None:
        return HttpResponse(status=404)
    try:
        pkpass = build_pkpass(cc)
    except AppleSigningError:
        return HttpResponse(status=503)
    resp = HttpResponse(pkpass, content_type="application/vnd.apple.pkpass")
    resp["Content-Disposition"] = f'attachment; filename="stampn-{cc.id}.pkpass"'
    return resp
