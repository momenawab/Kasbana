"""WSGI config for the Kasbana backend."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kasbana.settings')

application = get_wsgi_application()
