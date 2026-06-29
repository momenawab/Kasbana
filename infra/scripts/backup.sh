#!/usr/bin/env bash
#
# Nightly Postgres backup. Dumps the DB from the running container, gzips it to
# /opt/stampn/backups, and prunes dumps older than 7 days.
#
# Install as a cron job (run on the server):
#   (crontab -l 2>/dev/null; echo "30 2 * * * /opt/stampn/infra/scripts/backup.sh >> /opt/stampn/backups/backup.log 2>&1") | crontab -
#
# To send off-box (recommended), set BACKUP_S3=s3://your-bucket/stampn and have
# the AWS CLI configured; the dump is uploaded after each run.

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/
set -a; [ -f .env ] && . ./.env; set +a

BACKUP_DIR=/opt/stampn/backups
mkdir -p "$BACKUP_DIR"
TS=$(date +%F-%H%M)
OUT="$BACKUP_DIR/stampn-$TS.sql.gz"

echo "▶ Dumping database to $OUT"
docker compose -f compose.prod.yml exec -T db \
  pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "$OUT"

if [ -n "${BACKUP_S3:-}" ] && command -v aws >/dev/null 2>&1; then
  echo "▶ Uploading to $BACKUP_S3"
  aws s3 cp "$OUT" "$BACKUP_S3/"
fi

echo "▶ Pruning dumps older than 7 days"
find "$BACKUP_DIR" -name 'stampn-*.sql.gz' -mtime +7 -delete

echo "✓ Backup complete: $OUT"
