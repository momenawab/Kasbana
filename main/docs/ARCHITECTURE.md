# Architecture

## Source of truth: the `dev` branch

All work happens on **`dev`**, a monorepo:

```
dev/
  main/                      # docs → main branch
  frontend/                  # React app → frontend branch (+ build → deployment)
  backend/                   # Django API → Backend branch
  .github/workflows/distribute.yml
```

Pushing `dev` triggers `distribute.yml`, which publishes each folder to its
branch. The other branches are **generated** — never edit them directly.

## Components

### `frontend/` → `frontend` branch
- **Stack:** Vite + React (JavaScript), `react-router-dom`, `react-helmet-async`.
- **Bilingual:** English at `/`, Arabic (RTL) at `/ar`, with a header language
  switcher. All copy in `src/i18n/index.js`.
- **Form:** Support form posts to Web3Forms (no backend needed for email).
- **Build output:** `dist/` — static files, including `.htaccess` for SPA
  routing on Apache.

### `backend/` → `Backend` branch
- **Stack:** Django 5 + DRF, env-driven settings, CORS for the frontend.
- **Status:** scaffold ready; feature apps added on top.

### Build → `deployment` branch
- The Action builds `frontend/` and publishes `dist/` to `deployment`.
- **Hostinger** serves `deployment` directly from the web root; `.htaccess`
  handles SPA rewrites and caching.

### `main/` → `main` branch
- Docs and project overview only (this folder).

## CI/CD

`.github/workflows/distribute.yml` (runs on push to `dev`):

1. `main/` → `main` (force-orphan)
2. `frontend/` → `frontend` (force-orphan)
3. `backend/` → `Backend` (force-orphan)
4. `npm ci && npm run build` in `frontend/`, then `dist/` → `deployment`
5. Hostinger redeploys from `deployment`

All pushes use `GITHUB_TOKEN`, so steps don't re-trigger each other (no loops).

## Domains & contact

- Canonical domain: `https://stampn.net`
- Contact email: `contact@stampn.net`

Set in `frontend/src/config.js`.
