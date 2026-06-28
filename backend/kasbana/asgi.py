"""ASGI config for the Kasbana backend."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kasbana.settings')

application = get_asgi_application()
