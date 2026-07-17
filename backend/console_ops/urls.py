from django.urls import path

from .views import (
    OpsAlertListView,
    OpsDashboardView,
    OpsRefreshView,
    OpsSettingsView,
    TelegramTestView,
    WidgetView,
)

urlpatterns = [
    path("dashboard", OpsDashboardView.as_view()),
    path("refresh", OpsRefreshView.as_view()),
    path("alerts", OpsAlertListView.as_view()),
    path("settings", OpsSettingsView.as_view()),
    path("telegram/test", TelegramTestView.as_view()),
    path("widget", WidgetView.as_view()),
]
