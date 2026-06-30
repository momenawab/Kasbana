#!/usr/bin/env bash
#
# Nightly Postgres backup. Dumps the DB from the running container, gzips it to
# /opt/stampn/backups, ships it OFF the box (so a dead server ≠ lost data), and
# prunes local dumps older than 7 days.
#
# Install as a cron job (run on the server):
#   (crontab -l 2>/dev/null; echo "30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1") | crontab -
#
# Off-box (STRONGLY recommended — a backup that only lives on the same server is
# not a backup): set BACKUP_S3=s3://your-bucket/stampn in infra/.env and have the
# AWS CLI configured (IAM with s3:PutObject). Each dump is uploaded after it's
# written; the run FAILS LOUDLY if the upload can't happen, so cron logs catch it.

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/
set -a; [ -f .env ] && . ./.env; set +a

BACKUP_DIR=/opt/stampn/backups
mkdir -p "$BACKUP_DIR"
TS=$(date +%F-%H%M)
OUT="$BACKUP_DIR/stampn-$TS.sql.gz"

echo "▶ Dumping database to $OUT"
# --no-owner/--no-acl keep the dump portable so it restores cleanly under any
# role (matters for verify_backup.sh's throwaway Postgres and disaster recovery).
docker compose -f compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER}" --no-owner --no-acl "${POSTGRES_DB}" | gzip > "$OUT"

# Integrity gate: a truncated/empty dump is worse than useless (it can mask a
# real backup failure). Verify the gzip is valid and not trivially small.
SIZE=$(wc -c < "$OUT")
if ! gzip -t "$OUT" 2>/dev/null || [ "$SIZE" -lt 200 ]; then
  echo "✗ Backup looks corrupt/empty ($SIZE bytes) — removing and failing"
  rm -f "$OUT"
  exit 1
fi
echo "✓ Dump OK ($SIZE bytes)"

if [ -n "${BACKUP_S3:-}" ]; then
  if ! command -v aws >/dev/null 2>&1; then
    echo "✗ BACKUP_S3 is set but the AWS CLI is not installed — cannot ship off-box"
    exit 1
  fi
  echo "▶ Uploading to $BACKUP_S3"
  aws s3 cp "$OUT" "$BACKUP_S3/"   # set -e fails the run if this errors
  echo "✓ Off-box copy stored"
else
  echo "⚠ BACKUP_S3 is not set — this dump lives ONLY on this server."
  echo "  If the box is lost, so is this backup. Set BACKUP_S3 in infra/.env."
fi

echo "▶ Pruning local dumps older than 7 days"
find "$BACKUP_DIR" -name 'stampn-*.sql.gz' -mtime +7 -delete

echo "✓ Backup complete: $OUT"
