"""Revenue analytics serializers (Phase 7)."""

from __future__ import annotations

from rest_framework import serializers


class RevenueKpisSerializer(serializers.Serializer):
    mrr = serializers.DecimalField(max_digits=14, decimal_places=2)
    arr = serializers.DecimalField(max_digits=16, decimal_places=2)
    arpu = serializers.DecimalField(max_digits=12, decimal_places=2)
    ltv = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    paying_merchants = serializers.IntegerField()
    active_trials = serializers.IntegerField()
    comped_merchants = serializers.IntegerField()
    trial_to_paid_conversion = serializers.FloatField()
    logo_churn_rate = serializers.FloatField()
    revenue_churn_rate = serializers.FloatField()
    net_revenue_retention = serializers.FloatField(allow_null=True)


class RevenueByPlanSerializer(serializers.Serializer):
    plan = serializers.CharField()
    paying_merchants = serializers.IntegerField()
    mrr = serializers.DecimalField(max_digits=14, decimal_places=2)


class MonthlyRevenueSerializer(serializers.Serializer):
    month = serializers.CharField()
    collected_egp = serializers.DecimalField(max_digits=14, decimal_places=2)
    paid_invoices = serializers.IntegerField()
    new_payers = serializers.IntegerField()


class CohortRetentionSerializer(serializers.Serializer):
    cohort_month = serializers.CharField()
    size = serializers.IntegerField()
    still_paying = serializers.IntegerField()
    retention_pct = serializers.FloatField()


class RevenueAnalyticsSerializer(serializers.Serializer):
    range = serializers.DictField()
    kpis = RevenueKpisSerializer()
    revenue_by_plan = RevenueByPlanSerializer(many=True)
    monthly_series = MonthlyRevenueSerializer(many=True)
    cohort_retention = CohortRetentionSerializer(many=True)


# ── Platform analytics (Phase 8) ───────────────────────────────────────────────
class MerchantCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    trialing = serializers.IntegerField()
    past_due = serializers.IntegerField()
    churned = serializers.IntegerField()
    suspended = serializers.IntegerField()


class PlatformTotalsSerializer(serializers.Serializer):
    customers = serializers.IntegerField()
    cards = serializers.IntegerField()
    stamps = serializers.IntegerField()
    redemptions = serializers.IntegerField()


class WalletSplitSerializer(serializers.Serializer):
    apple = serializers.IntegerField()
    google = serializers.IntegerField()


class FeatureAdoptionSerializer(serializers.Serializer):
    key = serializers.CharField()
    merchants = serializers.IntegerField()
    pct = serializers.FloatField()


class GrowthPointSerializer(serializers.Serializer):
    month = serializers.CharField()
    new_merchants = serializers.IntegerField()
    cumulative = serializers.IntegerField()


class FunnelStageSerializer(serializers.Serializer):
    stage = serializers.CharField()
    count = serializers.IntegerField()


class TopMerchantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    activity = serializers.IntegerField()
    customers = serializers.IntegerField()


class PlatformAnalyticsSerializer(serializers.Serializer):
    merchants = MerchantCountsSerializer()
    totals = PlatformTotalsSerializer()
    wallet = WalletSplitSerializer()
    feature_adoption = FeatureAdoptionSerializer(many=True)
    growth = GrowthPointSerializer(many=True)
    funnel = FunnelStageSerializer(many=True)
    top_merchants = TopMerchantSerializer(many=True)
