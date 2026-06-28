#!/usr/bin/env bash
#
# Deploy a release on the EC2 box. Invoked by the deploy-prod workflow over SSH,
# or manually. Pulls the CI-built image, runs migrations, then rolls the stack.
#
#   IMAGE_TAG=<sha> bash scripts/deploy.sh
#
# Run from /opt/kasbana/infra (so ./.env and ./caddy/Caddyfile resolve).

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

echo "▶ Reloading Caddy config"
$COMPOSE exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile 2>/dev/null \
  || $COMPOSE restart caddy

echo "▶ Pruning old images"
docker image prune -f >/dev/null || true

echo "✓ Deploy complete."
$COMPOSE ps
