#!/usr/bin/env bash
#
# Stampn onboarding — clone the repo and set up an identical local environment.
#
# Usage:
#   curl -fsSL <raw-url>/scripts/onboard.sh | bash      # fresh machine
#   ./scripts/onboard.sh                                 # from inside a clone
#
# What it does:
#   1. Clones github.com/momenawab/Stampn (if not already inside it) on `dev`
#   2. Backend: venv + deps + .env + migrate + run tests
#   3. Frontend: npm install (if Node is available)
#   4. Prints the golden push-flow rules (dev distribution + prod deploy)
#
# Prereqs: git, python3 (3.11+), and optionally node/npm. You need write access
# to the repo (ask Momen to add you as a collaborator) to push to `dev`.

set -euo pipefail

REPO_URL="https://github.com/momenawab/Stampn.git"
BRANCH="dev"

say()  { printf "\n\033[1;36m▶ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m! %s\033[0m\n" "$*"; }

PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "python3 is required"; exit 1; }

# ── 1. Locate or clone the repo ───────────────────────────────────────────────
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && \
   git remote get-url origin 2>/dev/null | grep -qi "Stampn"; then
  ROOT="$(git rev-parse --show-toplevel)"
  say "Using existing clone at $ROOT"
else
  say "Cloning $REPO_URL"
  git clone "$REPO_URL"
  ROOT="$(pwd)/Stampn"
fi
cd "$ROOT"

say "Switching to '$BRANCH' (the single source of truth)"
git checkout "$BRANCH"
git pull origin "$BRANCH" || warn "Could not pull — continuing with local state"

# ── 2. Backend ────────────────────────────────────────────────────────────────
say "Backend: virtualenv + dependencies"
cd "$ROOT/backend"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements-dev.txt

[ -f .env ] || { cp .env.example .env; ok "created backend/.env from .env.example"; }

say "Backend: migrate + test"
python manage.py migrate
pytest -q

ok "Backend ready. Run it with:  cd backend && source .venv/bin/activate && python manage.py runserver"

# ── 3. Frontend (optional) ────────────────────────────────────────────────────
if command -v npm >/dev/null 2>&1; then
  say "Frontend: npm install"
  cd "$ROOT/frontend"
  npm install
  ok "Frontend ready. Run it with:  cd frontend && npm run dev"
else
  warn "npm not found — skipping frontend setup (install Node.js if you need it)"
fi

# ── 4. Golden rules ───────────────────────────────────────────────────────────
cat <<'RULES'

────────────────────────────────────────────────────────────────────────────
 STAMPN — HOW THE REPO WORKS  (read this once)
────────────────────────────────────────────────────────────────────────────
 • You edit ONLY the `dev` branch. It is a monorepo:
       dev/
         main/      → docs              (auto-published to `main` branch)
         frontend/  → React app         (auto-published to `frontend` branch)
         backend/   → Django API        (auto-published to `Backend` branch)
         infra/     → DevOps (docker)   (auto-published to `infra` branch)
         contracts/ → frozen openapi.yaml (the API source of truth)

 • Pushing to `dev` triggers .github/workflows/distribute.yml, which fans each
   folder out to its own branch automatically, AND backend-ci.yml (ruff · black
   · mypy · pytest) on any backend change. Keep CI green.
   NEVER edit the main/frontend/Backend/infra/deployment branches directly —
   they are generated and will be overwritten on the next dev push.

 • Ship a change:
       git add -A
       git commit -m "your message"
       git push origin dev          # → CI runs, branches distribute (NO deploy)

 • Production is a SEPARATE, deliberate step (Momen owns deploys). Promoting
   dev → prod triggers deploy-prod.yml (build image → GHCR → roll onto EC2):
       git checkout prod && git merge --ff-only dev && git push origin prod
       git checkout dev
   Live: https://api.stampn.net  ·  admin https://admin.stampn.net/admin/

 • Ownership (Backend Plan & Variable Contract, see main/docs/):
       Momen → core, common, config, enrollment, wallets, billing, infra
       Joe   → loyalty, dashboard
   Edit only your own apps. core/ + common/ + contracts/ change only by a
   reviewed PR. Import shared names from core/ — never redefine them.
────────────────────────────────────────────────────────────────────────────
RULES

ok "Onboarding complete 🎉"
