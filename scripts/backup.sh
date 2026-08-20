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

# ── Sentry cron monitoring ────────────────────────────────────────────────────
# A silently broken backup is worse than none, because you believe you're
# covered. This script sat unscheduled for 17 days and nobody noticed — the
# script was fine, nothing was watching. Sentry alerts when a check-in doesn't
# arrive on schedule, which is the only way that failure mode is ever visible.
#
# Reuses SENTRY_DSN from .env (no new secret) and derives the check-in URL from
# it. Create the monitor first: Sentry -> Crons -> slug `stampn-backup`,
# schedule `30 2 * * *`. Empty SENTRY_DSN disables this silently.
#
# A check-in NEVER fails the backup — a Sentry outage must not cost you a dump.
SENTRY_MONITOR_SLUG="${SENTRY_MONITOR_SLUG:-stampn-backup}"

sentry_checkin() {
  [ -n "${SENTRY_DSN:-}" ] || return 0
  command -v curl >/dev/null 2>&1 || return 0
  # DSN shape: https://<key>@<host>/<project_id>
  local rest key host project
  rest=${SENTRY_DSN#*//}
  key=${rest%%@*}
  host=${rest#*@}; host=${host%%/*}
  project=${SENTRY_DSN##*/}
  curl -fsS -m 10 -o /dev/null \
    "https://${host}/api/${project}/cron/${SENTRY_MONITOR_SLUG}/${key}/?status=$1" \
    2>/dev/null || echo "⚠ Sentry check-in ($1) failed — the backup itself is unaffected"
  return 0
}

# Report on ANY non-zero exit, not just a clean finish: the integrity gate
# (exit 1) and the S3 upload failure are exactly the cases worth alerting on.
trap 'rc=$?; [ "$rc" -eq 0 ] || sentry_checkin error' EXIT

sentry_checkin in_progress

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

# Only reached if the dump passed the integrity gate AND (if configured) the
# off-box copy landed — so an "ok" here means the backup is genuinely safe,
# not merely that the script ran.
sentry_checkin ok

echo "▶ Recording backup to Stampn Ops"
docker compose -f compose.prod.yml -f compose.ops-collector.yml run --rm web python manage.py ops_record_backup --size "$SIZE" || true

echo "✓ Backup complete: $OUT"
