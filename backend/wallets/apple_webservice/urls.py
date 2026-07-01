"""Apple Wallet web-service URLs (Apple's external spec — camelCase paths).

Mounted at /api/v1/wallet/apple/ so Apple's webServiceURL of
``{BASE_URL}/api/v1/wallet/apple`` resolves the ``/v1/...`` sub-paths.
"""

from django.urls import path

from wallets.apple_webservice import views

urlpatterns = [
    path(
        "v1/devices/<str:device_library_id>/registrations/<str:pass_type_id>/<str:serial>",
        views.register_device,
        name="apple-register",
    ),
    path(
        "v1/devices/<str:device_library_id>/registrations/<str:pass_type_id>",
        views.list_updated_serials,
        name="apple-list",
    ),
    path("v1/passes/<str:pass_type_id>/<str:serial>", views.get_pass, name="apple-pass"),
    path("v1/log", views.log, name="apple-log"),
    path("download/<uuid:customer_card_id>", views.download_pass, name="apple-download"),
]
