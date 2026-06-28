"""
Django settings for the Kasbana backend.

Configuration is driven by environment variables (see .env.example). For local
development, copy .env.example to .env and adjust as needed.
"""

from pathlib import Path
import os

# Optionally load a local .env file if python-dotenv is installed.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(os.environ.get(key, default)).lower() in {'1', 'true', 'yes', 'on'}


def env_list(key, default=''):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────────────────────────
# Generate a real key for production:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-insecure-change-me')

DEBUG = env_bool('DJANGO_DEBUG', True)

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', 'https://kasbana.net')

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    # Local apps go here as you build them, e.g.:
    # 'cards',
    # 'businesses',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # must be before CommonMiddleware
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'kasbana.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'kasbana.wsgi.application'
ASGI_APPLICATION = 'kasbana.asgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
# Defaults to SQLite for local dev. Point DATABASE_* at MySQL/Postgres for prod.
if env('DATABASE_ENGINE'):
    DATABASES = {
        'default': {
            'ENGINE': env('DATABASE_ENGINE'),
            'NAME': env('DATABASE_NAME', 'kasbana'),
            'USER': env('DATABASE_USER', ''),
            'PASSWORD': env('DATABASE_PASSWORD', ''),
            'HOST': env('DATABASE_HOST', 'localhost'),
            'PORT': env('DATABASE_PORT', ''),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalization ──────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'Africa/Cairo')
USE_I18N = True
USE_TZ = True

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS (allow the React frontend to call the API) ───────────────────────────
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,https://kasbana.net',
)

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
}
