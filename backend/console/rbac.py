"""Central RBAC permission matrix (Phase 12) — the single source of truth.

Every admin gate in the console derives from ``ROLE_PERMISSIONS`` here. The
per-domain permission classes in ``console.permissions`` (``IsFinanceAdmin``,
``IsSupportAdmin``, ``IsMarketingAdmin``) are thin lookups against this matrix,
so there is exactly one place that answers "which role may do what". Reads
(list/detail) stay open to any active admin (the ``IsAdminUser`` base) — the
matrix gates *mutations* and sensitive tools.

Super-admin implicitly holds every permission (see ``permissions_for``); the
other roles hold an explicit subset. ``READ_ONLY`` and (for now) ``ENGINEERING``
hold none — Engineering's ops permissions land with Phase 14.
"""

from __future__ import annotations

from console.enums import AdminRole


class Permission:
    """Granular capability keys. Grouped by the phase that introduced the gate."""

    PLANS_MANAGE = "plans.manage"  # Phase 3 — create/edit/archive plans
    SUBSCRIPTIONS_MANAGE = "subscriptions.manage"  # Phase 4 — plan/status/comp/lock
    BILLING_MANAGE = "billing.manage"  # Phase 5 — retry/manual invoice/dunning
    REVENUE_VIEW = "revenue.view"  # Phase 7 — financial analytics
    SUPPORT_TOOLS = "support.tools"  # Phase 6 — impersonation, notes, account fixes
    MERCHANTS_MODERATE = "merchants.moderate"  # Phase 9 — flag queue / moderation
    MERCHANTS_SUSPEND = "merchants.suspend"  # Phase 9 — suspend/ban a merchant
    ANNOUNCEMENTS_MANAGE = "announcements.manage"  # Phase 10 — broadcasts
    PROMOTIONS_MANAGE = "promotions.manage"  # Phase 11 — coupons / promotions
    ADMINS_MANAGE = "admins.manage"  # Phase 12 — manage the admin team
    COMPLIANCE_EXPORT = "compliance.export"  # Phase 13 — export a merchant's data bundle (PII)
    COMPLIANCE_DELETE = "compliance.delete"  # Phase 13 — right-to-be-forgotten merchant delete
    RETENTION_MANAGE = "retention.manage"  # Phase 13 — edit the data-retention policy
    OPS_MANAGE = "ops.manage"  # Phase 14 — flags/settings/maintenance, job & webhook retries
    PARTNERS_MANAGE = "partners.manage"  # Phase E.1 — referral partners + reward config
    LEADS_MANAGE = "leads.manage"  # CRM — create/edit/assign leads, log calls
    LEADS_CONVERT = "leads.convert"  # CRM — convert a lead into a live merchant
    CRM_CONFIGURE = "crm.configure"  # CRM — edit the configurable dropdowns
    # Lead generation. Running a job spends real money (Places is billed per
    # call), so starting one is gated separately from reading the results —
    # everyone can look at the pipeline, not everyone can put it on the bill.
    LEADGEN_RUN = "leadgen.run"  # create/start/pause/cancel/retry a search job
    LEADGEN_IMPORT = "leadgen.import"  # push a generated lead into the CRM


ALL_PERMISSIONS: frozenset[str] = frozenset(
    value
    for name, value in vars(Permission).items()
    if not name.startswith("_") and isinstance(value, str)
)


# The matrix. Super-admin is intentionally absent here — it holds *everything*
# (resolved in ``permissions_for``) so a newly added permission is granted to
# super-admin by default and never silently withheld.
#
# The Phase 13 compliance keys (COMPLIANCE_EXPORT/DELETE, RETENTION_MANAGE) are
# deliberately in NO role's set below: they are super-admin-only. Merchant delete
# is irreversible and export dumps cross-tenant PII, so these stay the sharpest
# tools in the box — held only by the role that implicitly holds everything.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    AdminRole.FINANCE: frozenset(
        {
            Permission.PLANS_MANAGE,
            Permission.SUBSCRIPTIONS_MANAGE,
            Permission.BILLING_MANAGE,
            Permission.REVENUE_VIEW,
            Permission.PROMOTIONS_MANAGE,
            Permission.PARTNERS_MANAGE,
        }
    ),
    AdminRole.SUPPORT: frozenset(
        {
            Permission.SUPPORT_TOOLS,
            Permission.MERCHANTS_MODERATE,
        }
    ),
    AdminRole.MARKETING_ADMIN: frozenset({Permission.ANNOUNCEMENTS_MANAGE}),
    AdminRole.ENGINEERING: frozenset({Permission.OPS_MANAGE}),  # platform ops (Phase 14)
    # Sales works the lead pipeline and closes it. LEADS_CONVERT provisions a
    # real merchant + subscription, which is otherwise Finance's ground — it sits
    # here because closing a lead *is* the sales job, and the conversion can only
    # ever create an account, never re-price or refund an existing one. Note the
    # absence of CRM_CONFIGURE: reshaping everyone's dropdowns is platform config,
    # so it stays super-admin-only alongside the other config keys.
    # Lead generation belongs to Sales for the same reason the CRM does: the
    # people who work the pipeline are the ones who decide what should be in it.
    AdminRole.SALES: frozenset(
        {
            Permission.LEADS_MANAGE,
            Permission.LEADS_CONVERT,
            Permission.LEADGEN_RUN,
            Permission.LEADGEN_IMPORT,
        }
    ),
    AdminRole.READ_ONLY: frozenset(),  # view everything, mutate nothing
}


# Roles for which MFA is mandatory (flag per role — Phase 12 declares it, Phase 15
# enforces it at login). Any role holding a mutating permission is privileged.
MFA_REQUIRED_ROLES: frozenset[str] = frozenset(
    {
        AdminRole.SUPER_ADMIN,
        AdminRole.FINANCE,
        AdminRole.SUPPORT,
        AdminRole.MARKETING_ADMIN,
        AdminRole.ENGINEERING,  # holds OPS_MANAGE since Phase 14 → now privileged
        AdminRole.SALES,  # mutates leads + reads a pipeline full of contact PII
    }
)


def permissions_for(role: str) -> frozenset[str]:
    """Every permission a role holds (super-admin holds all)."""
    if role == AdminRole.SUPER_ADMIN:
        return ALL_PERMISSIONS
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_can(role: str, permission: str) -> bool:
    """Whether ``role`` may exercise ``permission`` — the one authority check."""
    return permission in permissions_for(role)


def mfa_required(role: str) -> bool:
    return role in MFA_REQUIRED_ROLES
