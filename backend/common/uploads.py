"""Image upload validation + storage — one implementation, two boundaries.

The merchant dashboard (``POST /uploads``, merchant JWT) and the admin console's
lead-logo upload (``POST /admin/v1/leads/{id}/logo``, admin JWT) both take an
image from a user and put it in storage. They authenticate completely
differently and always will; what must never differ is what they *accept*.

Hence this module. The rules here are a security boundary, not a convenience:
SVG is excluded because it executes script when served (stored XSS), and the
declared content-type is cross-checked against the extension because a caller
controls both and will happily claim ``image/png`` for a ``.svg``. Duplicating
that per endpoint is how one copy quietly falls behind the other.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from common.errors import PayloadTooLarge, UnprocessableEntity

# Content-type → the extensions it may legitimately carry. SVG is deliberately
# absent: it is an executable document, and serving one from our own origin
# hands an attacker script execution against our users.
UPLOAD_TYPE_MAP: dict[str, frozenset[str]] = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/webp": frozenset({".webp"}),
}

ALLOWED_EXTENSIONS: frozenset[str] = frozenset().union(*UPLOAD_TYPE_MAP.values())


def save_image(file_obj, *, prefix: str = "uploads") -> str:
    """Validate ``file_obj`` and store it. Returns the storage path.

    Raises ``PayloadTooLarge`` / ``UnprocessableEntity`` — both DomainErrors, so
    each boundary renders them in its own error shape without either knowing
    about the other.

    ``prefix`` separates what came from where in storage; it is not a security
    control (the checks below are), just a way to keep merchant uploads and
    lead logos from sharing one undifferentiated folder.
    """
    if file_obj is None:
        raise UnprocessableEntity("No file provided.")

    if file_obj.size > settings.UPLOAD_MAX_SIZE_BYTES:
        raise PayloadTooLarge()

    ext = Path(file_obj.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or file_obj.content_type not in settings.UPLOAD_ALLOWED_TYPES:
        raise UnprocessableEntity("Unsupported file type.")
    # The caller controls both the name and the declared type, so agreement
    # between them is the check that matters — either alone is trivially forged.
    if ext not in UPLOAD_TYPE_MAP.get(file_obj.content_type, frozenset()):
        raise UnprocessableEntity("File extension does not match content type.")

    safe_name = re.sub(r"[^\w.\-]", "_", Path(file_obj.name).name)
    return default_storage.save(f"{prefix}/{timezone.now().timestamp()}_{safe_name}", file_obj)


def absolute_url(request, path: str) -> str:
    """The stored ``path`` as a URL the browser can fetch."""
    return request.build_absolute_uri(settings.MEDIA_URL + path)
