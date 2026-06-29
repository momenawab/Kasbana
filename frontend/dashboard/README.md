# Stampn — Client Dashboard

Merchant-facing dashboard (Direction C) at `frontend/dashboard/`. **Standalone app** — nested under
`frontend/` because it's client-facing, but independent of the marketing site at `frontend/` root (own
package.json/deps/config/build; no shared code). Built against `contracts/openapi.yaml`; see
`main/docs/Dashboard-Implementation-Plan.md` (phase plan) and `main/docs/Frontend-dashboard-plan.md`
(per-screen spec).

## Run

```bash
npm install
npx msw init public/ --save   # first time only — generates the mock worker
cp .env.example .env          # VITE_USE_MOCKS=1 to run on mocks, 0 to hit the real backend
npm run dev                   # http://localhost:5174
npm run build && npm run lint
```

- `VITE_USE_MOCKS=1` → all API calls served by MSW (`src/mocks/`).
- `VITE_USE_MOCKS=0` + `VITE_API_URL=<backend>` → real backend (`/api/v1`).

## Status: Phase 1 (scaffold) done

App shell (Direction-C `bg-ink` sidebar + bottom nav, Topbar with ع/EN toggle + trial chip), RTL/i18n
(`ar` default), axios client with 401-refresh, auth guard + session, routing with placeholder screens,
and a starter MSW layer (`/auth/token`, `/auth/refresh`, `/me` on a trial merchant).

Next: Phase 2 (design-system components + WalletPreview + usePlan gating). Feature screens (`src/features/*`)
are placeholders until their phase.
