"""Loyalty URLs (contract §3.6). Mounted under /api/v1/loyalty/."""

from django.urls import path

from loyalty.views import CardStateView, RedeemView, ScanView, StampView

urlpatterns = [
    path("stamp", StampView.as_view(), name="loyalty-stamp"),
    path("redeem", RedeemView.as_view(), name="loyalty-redeem"),
    path("scan", ScanView.as_view(), name="loyalty-scan"),
    path("cards/<uuid:customer_card_id>", CardStateView.as_view(), name="loyalty-card"),
]
