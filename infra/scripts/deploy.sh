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

COMPOSE="docker compose -f compose.prod.yml"

echo "▶ Deploying image tag: $IMAGE_TAG"

if [ ! -f .env ]; then
  echo "✗ Missing infra/.env on the server — copy .env.prod.example and fill it." >&2
  exit 1
fi

echo "▶ Pulling images"
$COMPOSE pull

echo "▶ Applying migrations"
$COMPOSE run --rm web python manage.py migrate --noinput

echo "▶ Starting / updating services"
$COMPOSE up -d

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
