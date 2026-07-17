"""Admin console URL routes — mounted at ``/api/admin/v1/`` (see config.urls)."""

from __future__ import annotations

from django.urls import path

from console.views import (
    AdminLoginView,
    AdminMeView,
    AdminRefreshView,
    AdminSessionListView,
    AdminSessionRevokeView,
    MfaConfirmView,
    MfaSetupView,
    MfaVerifyView,
    StepUpView,
)
from console.views_admins import (
    AdminActivityView,
    AdminDetailView,
    AdminListCreateView,
    AdminResetMfaView,
    RbacMatrixView,
)
from console.views_analytics import (
    PlatformAnalyticsView,
    RevenueAnalyticsView,
    RevenueExportView,
)
from console.views_announcements import (
    AnnouncementDetailView,
    AnnouncementListView,
    AnnouncementScheduleView,
    AnnouncementSendView,
    AudiencePreviewView,
)
from console.views_audit import AuditLogExportView, AuditLogListView
from console.views_billing import DunningListView, DunningNotifyView, ReconciliationView
from console.views_compliance import (
    MerchantConsentView,
    MerchantDataExportView,
    MerchantDeleteView,
    RetentionPolicyView,
)
from console.views_contact import (
    ContactMessageDetailView,
    ContactMessageListView,
    ContactReplyView,
)
from console.views_coupons import (
    ApplyCouponView,
    CouponDetailView,
    CouponGroupDetailView,
    CouponGroupListView,
    CouponListView,
    CouponRedemptionsView,
)
from console.views_invoices import (
    InvoiceDetailView,
    InvoiceListView,
    InvoiceRetryView,
    MerchantInvoiceCreateView,
)
from console.views_leads import LeadDetailView, LeadListView
from console.views_lifecycle import (
    AtRiskView,
    ModerationQueueView,
    ModerationScanView,
    PipelineView,
    ResolveFlagView,
    SuspendView,
    UnsuspendView,
)
from console.views_merchants import MerchantDetailView, MerchantListView
from console.views_ops import (
    FeatureFlagDetailView,
    FeatureFlagListView,
    FeatureFlagOverrideView,
    HealthView,
    MaintenanceView,
    PlatformSettingDetailView,
    PlatformSettingListView,
    TaskResultListView,
    TaskRetryView,
    WalletFailureListView,
    WalletReprovisionView,
    WebhookDeliveryListView,
    WebhookReplayView,
)
from console.views_partners import (
    PartnerConfigView,
    PartnerDetailView,
    PartnerListView,
    PartnerReferralsView,
)
from console.views_plans import PlanDetailView, PlanListView
from console.views_subscription import (
    AssignEnterpriseView,
    CompView,
    ExtendTrialView,
    LockView,
    MerchantSubscriptionView,
    SubscriptionAuditView,
    UnlockView,
)
from console.views_support import (
    ActivityView,
    ClearStuckCheckoutView,
    ImpersonateView,
    ImpersonationEndView,
    ImpersonationListView,
    MerchantContactMessagesView,
    ResendInviteView,
    SendPasswordResetView,
    SupportNotesView,
)

urlpatterns = [
    path("auth/login", AdminLoginView.as_view(), name="admin-login"),
    path("auth/mfa/verify", MfaVerifyView.as_view(), name="admin-mfa-verify"),
    path("auth/refresh", AdminRefreshView.as_view(), name="admin-refresh"),
    path("auth/mfa/setup", MfaSetupView.as_view(), name="admin-mfa-setup"),
    path("auth/mfa/confirm", MfaConfirmView.as_view(), name="admin-mfa-confirm"),
    path("auth/step-up", StepUpView.as_view(), name="admin-step-up"),
    path("auth/sessions", AdminSessionListView.as_view(), name="admin-sessions"),
    path(
        "auth/sessions/<uuid:session_id>",
        AdminSessionRevokeView.as_view(),
        name="admin-session-revoke",
    ),
    path("me", AdminMeView.as_view(), name="admin-me"),
    # Merchant directory (Phase 2)
    path("merchants", MerchantListView.as_view(), name="admin-merchants"),
    path(
        "merchants/<uuid:merchant_id>", MerchantDetailView.as_view(), name="admin-merchant-detail"
    ),
    # Plan catalogue (Phase 3)
    path("plans", PlanListView.as_view(), name="admin-plans"),
    path("plans/<str:key>", PlanDetailView.as_view(), name="admin-plan-detail"),
    # Subscription management (Phase 4)
    path(
        "merchants/<uuid:merchant_id>/subscription",
        MerchantSubscriptionView.as_view(),
        name="admin-merchant-subscription",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/enterprise",
        AssignEnterpriseView.as_view(),
        name="admin-merchant-subscription-enterprise",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/extend-trial",
        ExtendTrialView.as_view(),
        name="admin-merchant-subscription-extend-trial",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/comp",
        CompView.as_view(),
        name="admin-merchant-subscription-comp",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/lock",
        LockView.as_view(),
        name="admin-merchant-subscription-lock",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/unlock",
        UnlockView.as_view(),
        name="admin-merchant-subscription-unlock",
    ),
    path(
        "merchants/<uuid:merchant_id>/subscription/audit",
        SubscriptionAuditView.as_view(),
        name="admin-merchant-subscription-audit",
    ),
    # Billing, invoices & dunning (Phase 5)
    path("invoices", InvoiceListView.as_view(), name="admin-invoices"),
    path("invoices/<uuid:invoice_id>", InvoiceDetailView.as_view(), name="admin-invoice-detail"),
    path(
        "invoices/<uuid:invoice_id>/retry", InvoiceRetryView.as_view(), name="admin-invoice-retry"
    ),
    path(
        "merchants/<uuid:merchant_id>/invoices",
        MerchantInvoiceCreateView.as_view(),
        name="admin-merchant-invoice-create",
    ),
    path("billing/dunning", DunningListView.as_view(), name="admin-billing-dunning"),
    path(
        "merchants/<uuid:merchant_id>/dunning/notify",
        DunningNotifyView.as_view(),
        name="admin-merchant-dunning-notify",
    ),
    path(
        "billing/reconciliation", ReconciliationView.as_view(), name="admin-billing-reconciliation"
    ),
    # Support tools & impersonation (Phase 6)
    path(
        "merchants/<uuid:merchant_id>/impersonate",
        ImpersonateView.as_view(),
        name="admin-merchant-impersonate",
    ),
    path(
        "merchants/<uuid:merchant_id>/impersonations",
        ImpersonationListView.as_view(),
        name="admin-merchant-impersonations",
    ),
    path("impersonate/end", ImpersonationEndView.as_view(), name="admin-impersonate-end"),
    path(
        "merchants/<uuid:merchant_id>/support/send-password-reset",
        SendPasswordResetView.as_view(),
        name="admin-merchant-send-password-reset",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/resend-invite",
        ResendInviteView.as_view(),
        name="admin-merchant-resend-invite",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/clear-stuck-checkout",
        ClearStuckCheckoutView.as_view(),
        name="admin-merchant-clear-stuck-checkout",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/notes",
        SupportNotesView.as_view(),
        name="admin-merchant-support-notes",
    ),
    path(
        "merchants/<uuid:merchant_id>/support/messages",
        MerchantContactMessagesView.as_view(),
        name="admin-merchant-support-messages",
    ),
    path(
        "merchants/<uuid:merchant_id>/activity",
        ActivityView.as_view(),
        name="admin-merchant-activity",
    ),
    # Revenue & financial analytics (Phase 7)
    path("analytics/revenue", RevenueAnalyticsView.as_view(), name="admin-analytics-revenue"),
    path(
        "analytics/revenue/export",
        RevenueExportView.as_view(),
        name="admin-analytics-revenue-export",
    ),
    # Platform analytics & usage (Phase 8)
    path("analytics/platform", PlatformAnalyticsView.as_view(), name="admin-analytics-platform"),
    # Lifecycle & moderation (Phase 9)
    path("lifecycle/pipeline", PipelineView.as_view(), name="admin-lifecycle-pipeline"),
    path("lifecycle/at-risk", AtRiskView.as_view(), name="admin-lifecycle-at-risk"),
    path(
        "merchants/<uuid:merchant_id>/suspend", SuspendView.as_view(), name="admin-merchant-suspend"
    ),
    path(
        "merchants/<uuid:merchant_id>/unsuspend",
        UnsuspendView.as_view(),
        name="admin-merchant-unsuspend",
    ),
    path("moderation/flags", ModerationQueueView.as_view(), name="admin-moderation-flags"),
    path("moderation/scan", ModerationScanView.as_view(), name="admin-moderation-scan"),
    path(
        "moderation/flags/<uuid:flag_id>/resolve",
        ResolveFlagView.as_view(),
        name="admin-moderation-resolve",
    ),
    # Communications & announcements (Phase 10)
    path("announcements", AnnouncementListView.as_view(), name="admin-announcements"),
    path(
        "announcements/audience-preview",
        AudiencePreviewView.as_view(),
        name="admin-announcement-audience-preview",
    ),
    path(
        "announcements/<uuid:announcement_id>",
        AnnouncementDetailView.as_view(),
        name="admin-announcement-detail",
    ),
    path(
        "announcements/<uuid:announcement_id>/send",
        AnnouncementSendView.as_view(),
        name="admin-announcement-send",
    ),
    path(
        "announcements/<uuid:announcement_id>/schedule",
        AnnouncementScheduleView.as_view(),
        name="admin-announcement-schedule",
    ),
    # Inbound "Get started" leads from the marketing site
    path("leads", LeadListView.as_view(), name="admin-leads"),
    path("leads/<uuid:lead_id>", LeadDetailView.as_view(), name="admin-lead-detail"),
    # Inbound support/contact messages from the marketing site
    path("messages", ContactMessageListView.as_view(), name="admin-messages"),
    path(
        "messages/<uuid:message_id>",
        ContactMessageDetailView.as_view(),
        name="admin-message-detail",
    ),
    path(
        "messages/<uuid:message_id>/reply",
        ContactReplyView.as_view(),
        name="admin-message-reply",
    ),
    # Coupons, discounts & promotions (Phase 11)
    path("coupon-groups", CouponGroupListView.as_view(), name="admin-coupon-groups"),
    path(
        "coupon-groups/<uuid:group_id>",
        CouponGroupDetailView.as_view(),
        name="admin-coupon-group-detail",
    ),
    path("coupons", CouponListView.as_view(), name="admin-coupons"),
    path("coupons/<str:code>", CouponDetailView.as_view(), name="admin-coupon-detail"),
    path(
        "coupons/<str:code>/redemptions",
        CouponRedemptionsView.as_view(),
        name="admin-coupon-redemptions",
    ),
    path(
        "merchants/<uuid:merchant_id>/apply-coupon",
        ApplyCouponView.as_view(),
        name="admin-merchant-apply-coupon",
    ),
    # Partner / merchant-referral program (Phase E.1)
    path("partner-config", PartnerConfigView.as_view(), name="admin-partner-config"),
    path("partners", PartnerListView.as_view(), name="admin-partners"),
    path("partners/<uuid:partner_id>", PartnerDetailView.as_view(), name="admin-partner-detail"),
    path(
        "partners/<uuid:partner_id>/referrals",
        PartnerReferralsView.as_view(),
        name="admin-partner-referrals",
    ),
    # Admin team & RBAC (Phase 12)
    path("admins", AdminListCreateView.as_view(), name="admin-admins"),
    path("admins/<uuid:admin_id>", AdminDetailView.as_view(), name="admin-admin-detail"),
    path(
        "admins/<uuid:admin_id>/activity",
        AdminActivityView.as_view(),
        name="admin-admin-activity",
    ),
    path(
        "admins/<uuid:admin_id>/reset-mfa",
        AdminResetMfaView.as_view(),
        name="admin-admin-reset-mfa",
    ),
    path("rbac/matrix", RbacMatrixView.as_view(), name="admin-rbac-matrix"),
    # Audit log viewer & compliance (Phase 13)
    path("audit", AuditLogListView.as_view(), name="admin-audit"),
    path("audit/export", AuditLogExportView.as_view(), name="admin-audit-export"),
    path("compliance/retention", RetentionPolicyView.as_view(), name="admin-compliance-retention"),
    path(
        "merchants/<uuid:merchant_id>/export",
        MerchantDataExportView.as_view(),
        name="admin-merchant-export",
    ),
    path(
        "merchants/<uuid:merchant_id>/consent",
        MerchantConsentView.as_view(),
        name="admin-merchant-consent",
    ),
    path(
        "merchants/<uuid:merchant_id>/erase",
        MerchantDeleteView.as_view(),
        name="admin-merchant-erase",
    ),
    # Platform operations, health & config (Phase 14)
    path("ops/health", HealthView.as_view(), name="admin-ops-health"),
    path("ops/flags", FeatureFlagListView.as_view(), name="admin-ops-flags"),
    path("ops/flags/<slug:key>", FeatureFlagDetailView.as_view(), name="admin-ops-flag-detail"),
    path(
        "ops/flags/<slug:key>/override",
        FeatureFlagOverrideView.as_view(),
        name="admin-ops-flag-override",
    ),
    path("ops/settings", PlatformSettingListView.as_view(), name="admin-ops-settings"),
    path(
        "ops/settings/<slug:key>",
        PlatformSettingDetailView.as_view(),
        name="admin-ops-setting-detail",
    ),
    path("ops/maintenance", MaintenanceView.as_view(), name="admin-ops-maintenance"),
    path("ops/tasks", TaskResultListView.as_view(), name="admin-ops-tasks"),
    path("ops/tasks/<str:task_id>/retry", TaskRetryView.as_view(), name="admin-ops-task-retry"),
    path("ops/webhooks", WebhookDeliveryListView.as_view(), name="admin-ops-webhooks"),
    path(
        "ops/webhooks/<uuid:delivery_id>/replay",
        WebhookReplayView.as_view(),
        name="admin-ops-webhook-replay",
    ),
    path("ops/wallet-failures", WalletFailureListView.as_view(), name="admin-ops-wallet-failures"),
    path(
        "ops/wallet-failures/<uuid:failure_id>/reprovision",
        WalletReprovisionView.as_view(),
        name="admin-ops-wallet-reprovision",
    ),
]
