"""Which mailbox an email leaves from — two of them, and the rule for choosing.

Stampn sends from two addresses, and the split is about whether a reply is
expected:

* ``donotreply@stampn.net`` — everything automated. Password resets, the
  Convert-To-Merchant setup link, staff invites, billing notices, product
  announcements. Nobody reads replies to it, and its name says so.
* ``contact@stampn.net`` — human correspondence. Today that is the admin
  replying to a contact-form message: a real person wrote to us, a real person
  answered, and the customer will answer back.

Two addresses means two SMTP *connections*, not one connection with a different
``From``. Hostinger authenticates a mailbox and then requires the From header to
name that same mailbox — a mismatch is rejected at the handshake with a 5.7.x,
so "log in as donotreply@ and claim to be contact@" does not send, it fails.
Hence ``support_connection()``: separate credentials, same server.

Django's default connection stays the ``donotreply@`` one, which makes the
common case free — every existing ``send_mail`` keeps working and keeps sending
from the right place. Only the support path has to say so explicitly.
"""

from __future__ import annotations

from django.conf import settings
from django.core.mail import get_connection


def support_connection():
    """An SMTP connection authenticated as the support mailbox.

    Falls back to the default connection when no support password is configured
    — which is the case in dev and CI, where ``EMAIL_BACKEND`` is the console or
    locmem backend and the credentials are meaningless anyway. Returning ``None``
    lets the caller pass it straight to ``EmailMessage(connection=...)``, where
    it means "use the default".
    """
    if not settings.SUPPORT_EMAIL_HOST_PASSWORD:
        return None
    return get_connection(
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.SUPPORT_EMAIL_HOST_USER,
        password=settings.SUPPORT_EMAIL_HOST_PASSWORD,
        use_ssl=settings.EMAIL_USE_SSL,
        use_tls=settings.EMAIL_USE_TLS,
        timeout=settings.EMAIL_TIMEOUT,
    )
