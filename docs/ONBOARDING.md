# Onboarding — getting a local copy running

This sets up an environment identical to the rest of the team's, with the same
`dev → component branches` push flow.

## One-command setup

**macOS / Linux / WSL / Git Bash**

```bash
git clone https://github.com/momenawab/Stampn.git
cd Stampn
./scripts/onboard.sh
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/momenawab/Stampn.git
cd Stampn
powershell -ExecutionPolicy Bypass -File .\scripts\onboard.ps1
```

The script clones (if needed), checks out `dev`, creates the backend virtualenv,
installs dependencies, writes `backend/.env`, runs migrations, runs the test
suite, and installs the frontend if Node is present.

> You need **write access** to push — ask Momen to add you as a collaborator.

## Prerequisites

- `git`, `python3` (3.11+); optionally `node`/`npm` for the frontend.

## How the repo works (the golden rules)

- **Edit only the `dev` branch.** It's a monorepo:

  ```
  dev/
    main/       → docs                (published to `main`)
    frontend/   → React app           (published to `frontend`)
    backend/    → Django API          (published to `Backend`)
    contracts/  → openapi.yaml         (frozen API source of truth)
  ```

- **Pushing `dev`** triggers two workflows:
  - `distribute.yml` — fans each folder out to its own branch (never edit those
    directly; they're regenerated on every push).
  - `backend-ci.yml` — runs ruff · black · mypy · pytest on backend changes.

- **Ship a change:**

  ```bash
  git add -A
  git commit -m "your message"
  git push origin dev
  ```

## Ownership (see `Walaa_Backend_Plan_and_Contract.md`)

| Owner | Apps |
|---|---|
| **Momen** | `core`, `common`, `config`, `enrollment`, `wallets`, `billing`, infra |
| **Joe** | `loyalty`, `dashboard` |

Edit only your own apps. `core/`, `common/` and `contracts/openapi.yaml` are
shared and change **only** through a reviewed PR. Import shared names from
`core/` — never redefine them locally.

## Daily commands

```bash
cd backend && source .venv/bin/activate
python manage.py runserver        # http://127.0.0.1:8000
pytest                            # run tests
ruff check . && black . && mypy . # quality gate (must be green for CI)
```

- API docs: http://127.0.0.1:8000/api/docs/
- Health: http://127.0.0.1:8000/api/health/
