#!/usr/bin/env bash
#
# Upsert KEY=VALUE lines from stdin into infra/.env, then leave the file in
# place for compose to read (compose.prod.yml: env_file: [.env]).
#
#   printf 'FOO=bar\nBAZ=qux\n' | bash scripts/upsert_env.sh
#
# Invoked by the deploy-prod workflow so GitHub secrets are the source of truth
# for credentials, instead of someone hand-editing .env over SSH and it silently
# drifting from what the runbook says is there.
#
# Two deliberate refusals:
#   * an EMPTY value is skipped, never written. A secret that isn't configured in
#     GitHub arrives as "" — blanking a working production value because someone
#     hasn't added the secret yet is the worst possible failure here.
#   * values are never echoed. Only key names and what happened to them.

set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/

ENV_FILE=.env

if [ ! -f "$ENV_FILE" ]; then
  echo "✗ Missing $PWD/$ENV_FILE — nothing to upsert into." >&2
  exit 1
fi

work=$(mktemp)
trap 'rm -f "$work" "$work.new"' EXIT
cp "$ENV_FILE" "$work"

changed=0

while IFS= read -r line || [ -n "$line" ]; do
  # Skip blanks and comments so the caller can send a readable block.
  [ -z "${line//[[:space:]]/}" ] && continue
  case "$line" in \#*) continue ;; esac
  case "$line" in *=*) ;; *) echo "· skipped (no '='): ${line%%=*}" ; continue ;; esac

  key=${line%%=*}
  value=${line#*=}

  # Keys are [A-Z0-9_] by convention; anything else would make the greps below
  # regex-unsafe, so refuse rather than corrupt the file.
  case "$key" in
    *[!A-Za-z0-9_]*|"") echo "· skipped (bad key): $key"; continue ;;
  esac

  if [ -z "$value" ]; then
    echo "· $key — empty in CI, leaving the server value untouched"
    continue
  fi

  if grep -q "^${key}=" "$work"; then
    current=$(grep -m1 "^${key}=" "$work"); current=${current#*=}
    if [ "$current" = "$value" ]; then
      echo "= $key unchanged"
      continue
    fi
    grep -v "^${key}=" "$work" > "$work.new" || true
    mv "$work.new" "$work"
    echo "~ $key updated"
  else
    echo "+ $key added"
  fi

  printf '%s=%s\n' "$key" "$value" >> "$work"
  changed=1
done

if [ "$changed" -eq 0 ]; then
  echo "✓ .env already current — no changes."
  exit 0
fi

# Keep one timestamped backup per change so a bad secret is recoverable without
# the console, and prune to the last 10 so this never fills the disk.
backup="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
(umask 077; cp "$ENV_FILE" "$backup")   # 0600 — a backup holds every secret too
ls -1t "${ENV_FILE}".bak.* 2>/dev/null | tail -n +11 | xargs -r rm -f

cat "$work" > "$ENV_FILE"   # rewrite in place: keeps owner/inode, compose is happy
chmod 600 "$ENV_FILE"

echo "✓ .env updated."
