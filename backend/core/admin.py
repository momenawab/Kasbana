"""Light admin registration to aid manual/staging inspection."""

from __future__ import annotations

from django.contrib import admin

from core import models


@admin.register(models.Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "plan", "created_at")
    search_fields = ("name", "slug", "legal_name")
    list_filter = ("status", "plan")


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "merchant", "address")
    list_filter = ("merchant",)


@admin.register(models.StaffUser)
class StaffUserAdmin(admin.ModelAdmin):
    list_display = ("user", "merchant", "role", "location", "is_active")
    list_filter = ("role", "is_active", "merchant")


@admin.register(models.Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("name", "merchant", "type", "stamps_required", "status")
    list_filter = ("type", "status", "merchant")


@admin.register(models.CustomerCard)
class CustomerCardAdmin(admin.ModelAdmin):
    list_display = ("customer_phone", "card", "stamp_count", "status", "enrolled_at")
    list_filter = ("status", "merchant")
    search_fields = ("customer_phone", "customer_name")
    readonly_fields = ("stamp_count", "auth_token")


@admin.register(models.StampLedger)
class StampLedgerAdmin(admin.ModelAdmin):
    list_display = ("customer_card", "event_type", "delta", "balance_after", "created_at")
    list_filter = ("event_type", "merchant")


admin.site.register(models.Reward)
admin.site.register(models.Redemption)
admin.site.register(models.EnrollmentToken)
admin.site.register(models.WalletRegistration)
