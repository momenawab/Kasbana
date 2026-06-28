"""URL configuration for the Kasbana backend."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(_request):
    """Simple health check so deploys can be verified."""
    return JsonResponse({'status': 'ok', 'service': 'kasbana-backend'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    # Add app routes here as you build them, e.g.:
    # path('api/', include('cards.urls')),
]
