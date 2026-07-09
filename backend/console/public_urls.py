"""Public marketing-facing routes — mounted under ``/api/v1/`` (see config.urls).

Unlike ``console.urls`` (the authenticated admin console), these are open to the
public marketing site. Kept separate so the admin auth boundary stays clean.
"""

from __future__ import annotations

from django.urls import path

from console.public import PublicLeadCreateView

urlpatterns = [
    path("leads", PublicLeadCreateView.as_view(), name="public-lead-create"),
]
