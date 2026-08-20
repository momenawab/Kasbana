"""Wallet web-service URLs (contract §3.6 · Phase 1.1).

Mounted under /api/v1/wallet/. The Apple Wallet web service (Apple's external
camelCase spec) is added in the Apple backend step.
"""

from django.urls import include, path

urlpatterns = [
    path("apple/", include("wallets.apple_webservice.urls")),
]
