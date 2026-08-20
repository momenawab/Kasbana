#!/usr/bin/env bash
#
# Disaster recovery — restore a backup into the PRODUCTION database.
# DESTRUCTIVE: this overwrites all current data and cannot be undone.
#
#   ./restore.sh /opt/stampn/backups/stampn-2026-06-30-0230.sql.gz
#
# To pull an off-box copy first:  aws s3 cp s3://your-bucket/stampn/<file> .
# Always confirm you have a fresh backup of the CURRENT state before restoring.

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/
set -a; [ -f .env ] && . ./.env; set +a

DUMP="${1:-}"
[ -z "$DUMP" ] && { echo "Usage: $0 <dump.sql.gz>"; exit 1; }
[ -f "$DUMP" ] || { echo "✗ Not found: $DUMP"; exit 1; }
gzip -t "$DUMP" 2>/dev/null || { echo "✗ Not a valid gzip: $DUMP"; exit 1; }

COMPOSE="docker compose -f compose.prod.yml"

echo "⚠️  This OVERWRITES the live database '${POSTGRES_DB}' with:"
echo "      $DUMP"
echo "    All current data will be replaced. This cannot be undone."
read -r -p "Type the database name (${POSTGRES_DB}) to confirm: " CONFIRM
[ "$CONFIRM" = "${POSTGRES_DB}" ] || { echo "Aborted."; exit 1; }

echo "▶ Stopping app containers (web/worker/beat) to drop DB connections…"
$COMPOSE stop web worker beat

echo "▶ Resetting the schema…"
$COMPOSE exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "▶ Restoring $DUMP…"
gunzip -c "$DUMP" | $COMPOSE exec -T db \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 >/dev/null

echo "▶ Restarting the stack…"
$COMPOSE up -d

echo "✓ Restore complete. Verify the app, then confirm a fresh nightly backup runs."
