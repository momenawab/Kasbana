"""Platform-admin enums — admin roles + audit actions.

These are the *platform operator's* roles (Stampn staff), entirely separate from
the merchant-side ``core.enums.Role`` (a shop's staff). The full per-role
permission matrix arrives in Phase 12; Phase 1 only needs the role field + the
SUPER_ADMIN check.
"""

from __future__ import annotations

from django.db import models


class AdminRole(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"  # everything, incl. admin-team mgmt
    FINANCE = "FINANCE", "Finance"  # billing, refunds, plans, revenue
    SUPPORT = "SUPPORT", "Support"  # merchant support, impersonation, notes
    MARKETING_ADMIN = "MARKETING_ADMIN", "Marketing Admin"  # announcements, promos
    ENGINEERING = "ENGINEERING", "Engineering"  # ops, health, feature flags
    READ_ONLY = "READ_ONLY", "Read Only"  # view everything, change nothing
