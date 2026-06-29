# Stampn backend image. Built in CI (GitHub Actions) and pulled by the EC2 box
# — the t3.small never builds. Build context is ./backend (see deploy-prod.yml).
#
#   docker build -f infra/docker/Dockerfile -t stampn-backend ./backend

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first for layer caching. psycopg[binary] bundles libpq, so no
# system build deps are needed.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code.
COPY . .

# Collect hashed static assets (served by WhiteNoise). A throwaway SECRET_KEY is
# fine — collectstatic does not touch the database.
RUN SECRET_KEY=build-only DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput

# Create the media dir so the mounted named volume inherits `app` ownership
# (a fresh volume copies the mount point's ownership from the image) — uploads
# (/media) are written here at uid 10001.
RUN mkdir -p /app/media

# Run as a non-root user.
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000

# Default command = web. compose overrides it for worker/beat.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "4", \
     "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
