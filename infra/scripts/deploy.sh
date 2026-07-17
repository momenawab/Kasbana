#!/usr/bin/env bash
#
# Deploy a release on the EC2 box. Invoked by the deploy-prod workflow over SSH,
# or manually. Pulls the CI-built image, runs migrations, then rolls the stack.
#
#   IMAGE_TAG=<sha> bash scripts/deploy.sh
#
# Run from /opt/stampn/infra (so ./.env and ./caddy/Caddyfile resolve).

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/

: "${IMAGE_TAG:?IMAGE_TAG is required (the image tag to deploy)}"
export IMAGE_TAG

COMPOSE="docker compose -f compose.prod.yml -f compose.ops-collector.yml"

echo "▶ Deploying image tag: $IMAGE_TAG"

if [ ! -f .env ]; then
  echo "✗ Missing infra/.env on the server — copy .env.prod.example and fill it." >&2
  exit 1
fi

# Auto-provision Stampn Ops secrets if missing
if ! grep -q "OPS_COLLECTOR_TOKEN" .env; then
  echo "▶ Auto-provisioning Stampn Ops secrets into .env"
  echo "" >> .env
  echo "# ── Stampn Ops ────────────────────────────────────────────────────────────────" >> .env
  echo "OPS_COLLECTOR_TOKEN=$(openssl rand -hex 32)" >> .env
  # Fake a Fernet key: 32 random bytes, base64url encoded
  echo "OPS_SETTINGS_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_' | cut -c1-43)=" >> .env
fi

echo "▶ Pulling images"
$COMPOSE pull

# Keep the local ``:latest`` tag pointing at the image we're deploying. Without
# this, a *manual* ``docker compose up -d`` (which resolves ${IMAGE_TAG:-latest}
# to :latest, and can't re-pull a private GHCR image without a fresh login)
# would silently recreate the stack on a STALE local :latest — reverting prod to
# old code. Retagging makes :latest == this release, so bare up -d stays current.
IMAGE="ghcr.io/momenawab/stampn-backend"
docker tag "${IMAGE}:${IMAGE_TAG}" "${IMAGE}:latest" || true

echo "▶ Applying migrations"
$COMPOSE run --rm web python manage.py migrate --noinput

echo "▶ Starting / updating services"
$COMPOSE up -d

echo "▶ Recording deployment"
$COMPOSE run --rm web python manage.py ops_record_deployment || true

# Force-recreate Caddy on its own so a changed Caddyfile is actually re-read.
# The Caddyfile is a single-file bind mount; `caddy reload` reads the old inode
# still bound in the running container ("config is unchanged"). Recreating
# re-binds the current file. --no-deps avoids re-pulling the app image (whose
# GHCR login is per-deploy and may have expired by now).
echo "▶ Recreating Caddy (pick up Caddyfile changes)"
$COMPOSE up -d --force-recreate --no-deps caddy

echo "▶ Pruning old images"
docker image prune -f >/dev/null || true

echo "✓ Deploy complete."
$COMPOSE ps
