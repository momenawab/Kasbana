#!/usr/bin/env bash
#
# Verified restore — proves the latest backup can actually be restored. Spins up
# a THROWAWAY Postgres, loads the newest dump into it, runs sanity checks, then
# tears it down. Never touches the production database.
#
# An untested backup is a guess; this turns it into a guarantee. Run weekly:
#   (crontab -l 2>/dev/null; echo "0 4 * * 0 /opt/stampn/infra/scripts/verify_backup.sh >> /opt/stampn/backups/verify.log 2>&1") | crontab -

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/

BACKUP_DIR=/opt/stampn/backups
LATEST=$(ls -1t "$BACKUP_DIR"/stampn-*.sql.gz 2>/dev/null | head -1 || true)
if [ -z "$LATEST" ]; then
  echo "✗ No backup found in $BACKUP_DIR — nothing to verify"
  exit 1
fi
echo "▶ Verifying restore of: $LATEST"

# 1. The file is a valid gzip.
gzip -t "$LATEST" 2>/dev/null || { echo "✗ Dump is not a valid gzip"; exit 1; }

NAME=stampn-restore-check
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
docker rm -f "$NAME" >/dev/null 2>&1 || true

echo "▶ Starting throwaway Postgres…"
docker run -d --name "$NAME" \
  -e POSTGRES_PASSWORD=verify -e POSTGRES_DB=verify \
  postgres:16-alpine >/dev/null

for _ in $(seq 1 30); do
  docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo "▶ Restoring the dump into it…"
gunzip -c "$LATEST" | docker exec -i "$NAME" \
  psql -U postgres -d verify -v ON_ERROR_STOP=1 >/dev/null

# 2. Schema loaded — Django's migration ledger must be present and populated.
MIGRATIONS=$(docker exec "$NAME" psql -U postgres -d verify -tAc \
  "SELECT count(*) FROM django_migrations;" 2>/dev/null || echo "ERR")
if [ "$MIGRATIONS" = "ERR" ] || [ "$MIGRATIONS" -lt 1 ]; then
  echo "✗ Restore loaded but django_migrations is missing/empty — backup is NOT trustworthy"
  exit 1
fi

# 3. App data is queryable (core_merchant is a foundational table).
MERCHANTS=$(docker exec "$NAME" psql -U postgres -d verify -tAc \
  "SELECT count(*) FROM core_merchant;" 2>/dev/null || echo "ERR")
if [ "$MERCHANTS" = "ERR" ]; then
  echo "✗ Restore loaded but core_merchant is unqueryable — backup is NOT trustworthy"
  exit 1
fi

echo "✓ Verified — restore succeeded ($MIGRATIONS migrations, $MERCHANTS merchants)."
