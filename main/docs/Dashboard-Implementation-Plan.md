# Kasbana Client Dashboard — Implementation Plan (Direction C)

> Executable build plan for the merchant-facing **Client Dashboard** React app, using the approved
> **Direction C — "Bold Modern"** visual template. Read alongside the per-screen spec
> `main/docs/Frontend-dashboard-plan.md` (the screen-by-screen source of truth, §6 API + §14 screens) and
> the API contract `contracts/openapi.yaml`. This document adds the locked design system, the architecture
> decisions, the live-vs-pending endpoint map, and a **fully detailed phase plan** — each phase lists its
> goal, files, build steps, API wiring, states/gating, and Definition of Done.
>
> **Strategy: contract-first, mock-where-needed.** The contract `openapi.yaml` is **complete and frozen**
> (the §6 dashboard endpoints are authored into it — see §4). Build each screen against the **real backend**
> when its endpoint is live, and against **MSW** when it isn't. Swapping a screen mock → real is a no-code
> flip (toggle MSW + set `VITE_API_URL`) once the endpoint lands on staging.
>
> **Backend status (2026-06-29).** Backend phases **1.0–1.5 are live** (auth + signup/forgot/reset/invite,
> `/me` + entitlements, settings, enrollment, wallets, loyalty stamp/redeem/cards, cards/customers/staff/
> locations CRUD, `analytics/summary`, entitlements engine + 14-day trial). In progress: **1.6** (cards
> stats/qr, uploads, customer detail/timeline, analytics timeseries/retention/by_location, activity,
> location/staff detail) and **1.7** (billing HTTP + Paymob/Fawry, messaging/WhatsApp, campaigns/segments/
> automations). Live list: `main/docs/Backend-Remaining-Tasks.md`.

---

## 1. Context

- Backend **1.0–1.5 are done**: Django backend (auth/account/settings, enrollment, wallets, loyalty,
  dashboard CRUD, entitlements + trial) + the **frozen, complete v1 API contract**
  (`contracts/openapi.yaml`, incl. the §6 dashboard paths). Backend **1.6/1.7** are in progress.
- The existing marketing site (`frontend/`) is a **separate, website-only build** — the dashboard is a
  **standalone app that shares nothing with it**: its own package.json, deps, config, i18n, and build.
  Do **not** import from, reuse, or restructure the marketing app.
- Deliverable = the whole **Client Dashboard** (every screen in spec §14): an Arabic-first (RTL),
  mobile-responsive React app where a merchant designs a stamp card, distributes it, watches customers +
  analytics, messages them, and manages team / locations / billing.
- Visual direction is **locked to Direction C** — `main/docs/mockups/dashboard/direction-c.html` is the
  reference for every screen (dark ink sidebar, colored KPI blocks, oversized mono numbers, high contrast,
  amber/ink/teal palette).
- New app = a **standalone Vite app at `frontend/dashboard/`** (own package.json/deps/config/build). It
  lives under `frontend/` because it's client-facing, but is **completely independent** of the marketing
  app at `frontend/` root — no shared deps, config, components, or i18n; the marketing app is untouched.
  v1 scope = **stamp cards only**; pricing = 14-day trial → Starter / Growth / Chain.
- **Sequencing:** frontend integrates each screen the moment its backend endpoint is live (1.0–1.5 already
  are); 1.6/1.7 screens stay on MSW until those land. Phase 8 re-verifies the mock-only screens, rather than
  being the first integration.

## 2. Locked design system (from `direction-c.html`)

`tailwind.config.js` `theme.extend` — copy verbatim from the mockup:

```js
colors: {
  ink:  { DEFAULT:'#0E1B2A', 2:'#16293D', 3:'#26405A' },
  amber:{ DEFAULT:'#E0A23B', d:'#C6862A', bg:'#FBF1DD' },
  clay: { DEFAULT:'#C75D43', bg:'#FAE7E0' },
  teal: { DEFAULT:'#1C7C73', bg:'#DFF0ED' },
  paper:'#FBF8F3', line:'#E7E1D6',
  tx:   { DEFAULT:'#1F2933', 2:'#566069', 3:'#8A949C' },
  success:'#1C7C73', warn:'#C6862A', danger:'#C0392B',
},
fontFamily: {
  head:['"Space Grotesk"','sans-serif'], body:['Inter','sans-serif'],
  ar:['Cairo','Tajawal','sans-serif'], mono:['"IBM Plex Mono"','monospace'],
},
borderRadius: { card:'16px', ctl:'10px' },
boxShadow: { bold:'0 12px 32px -10px rgba(14,27,42,.30)' },
```

**Direction-C styling rules (the "Bold Modern" identity):**
- Page bg `paper`, surfaces white with `border-line`; **sidebar = `bg-ink`** (amber active item),
  **chart card = `bg-ink`** with amber line + area gradient.
- **KPI tiles = solid color blocks** (amber→ink text; teal/clay/ink→white text), number in `font-mono`
  `text-[40px]/[44px]`, delta chip top-end.
- Headings `font-head` (Space Grotesk; Arabic falls back to Cairo, letter-spacing reset to 0 in RTL).
- Numbers use **`font-mono` + tabular-nums**, render **Arabic-Indic digits** in `ar` (`arDigits` helper).
- `shadow-bold` on elevated cards; decorative blurred amber blobs on dark surfaces.
- Mobile: sidebar → fixed bottom nav (`bg-ink`), first 5 nav items.

## 3. Stack & architecture decisions

- **Stack (spec §1):** React 18 + Vite 5 (JS) · react-router-dom 6 · @tanstack/react-query 5 · axios ·
  react-hook-form 7 + zod (`@hookform/resolvers`) · react-i18next + i18next · recharts · qrcode.react ·
  lucide-react · dayjs · Tailwind 3. eslint + prettier. (The mockup hand-rolls SVG/CDN; the real app uses
  the npm packages with the same token colors.)
- **App placement:** a **fully standalone Vite app at `frontend/dashboard/`** with its own `package.json`,
  `node_modules`, Vite + Tailwind config, and build. Nested under `frontend/` (it's client-facing) but shares
  **nothing** with the marketing app at `frontend/` root — no shared deps, config, components, or i18n. The
  marketing app is untouched.
- **CI/CD + serving (decided):** **subdomain**, not subpath. Marketing stays at `kasbana.net`; the dashboard
  is served at the **root of `app.kasbana.net`**, so routes are bare (`app.kasbana.net/login`, `/cards`) — no
  `/dashboard` URL prefix and no Vite `base`/router `basename`. The marketing "Login"/"Get started" CTAs link
  out to `app.kasbana.net`. The dashboard gets its **own** build + deploy target (separate from `frontend/`'s
  `distribute.yml`). Flag the `app.kasbana.net` DNS + deploy to infra; not blocking local dev (§8.2).
- **Mock layer:** **MSW** implements the §6 contract; toggled by env (`VITE_USE_MOCKS`). Handlers mirror the
  contract exactly so swap-to-real is no-code. Real API base = `VITE_API_URL + "/api/v1"`.
- **i18n:** `ar` default, `en` mirror; `ar.json` is source of truth; every visible string is a key. On
  language change set `document.documentElement.lang` + `dir`. **Logical utilities only**
  (`ps/pe/ms/me`, `text-start/end`, `start/end`) — never `pl/pr/left/right`.

## 4. Contract — done; live-vs-pending availability

The §6 dashboard endpoints are in `contracts/openapi.yaml` (paths + schemas, snake_case keys, EGP money,
cursor pagination `{next,previous,results}`, error shape `{error:{code,message,fields}}`), tagged
`x-status: dashboard-proposed`. The contract is **complete and authoritative**; the backend implements
those exact paths. This map drives mock-vs-real per screen:

- **Live now (1.0–1.5)** — integrate directly: `auth/token|refresh`, `auth/signup|forgot|reset|invite/{t}`,
  `GET /me` (+ entitlements), `settings/business|account|account/password`, `enroll/{token}`,
  `loyalty/stamp|redeem|cards/{id}`, `cards` (list/create/detail), `customers` (list), `staff` (list/create),
  `locations` (list/create), `analytics/summary`, Apple Wallet.
- **Pending — keep on MSW until live:**
  - **Backend 1.6:** `cards/{id}/stats`, `cards/{id}/qr`, `POST /uploads`, `GET/DELETE customers/{id}`,
    `customers/{id}/timeline`, `analytics/timeseries|retention|by_location`, `activity`,
    `PATCH locations/{id}`, `locations/{id}/stats`, `PATCH staff/{id}`, `POST staff/invite`.
  - **Backend 1.7:** `billing` (GET / subscribe / invoices / cancel / webhooks), `customers/{id}/message`,
    `campaigns`, `segments`, `automations`.
- Drop the `x-status: dashboard-proposed` tag per-path as each lands on staging.

> **Enum note:** the backend maps `plan`/`status` to the contract's lowercase values (incl. `trial`) at the
> API layer — the frontend consumes the contract values as-is.

## 5. Mockup → React component map (Direction C)

| Mockup region | React target |
|---|---|
| `<aside>` dark ink nav + bottom nav | `layout/Sidebar.jsx` (+ responsive bottom nav) |
| Topbar: logo, ع/EN toggle, trial chip, account menu | `layout/Topbar.jsx` |
| Trial banner (ink, amber CTA) | `components/Banner.jsx` |
| KPI color blocks | `components/KpiTile.jsx` (Direction-C `block`/`num`/`chip` variants) |
| Dark chart card + metric switch | `components/ChartLine.jsx` (recharts) + local metric tab state |
| Recent activity list | Overview-local `ActivityFeed` |
| Quick actions (dark cards) | Overview-local section |
| `arDigits`, AR/EN string map | `lib/format.js`, `lib/i18n.js` + `locales/*` |

The same shell/tokens/components dress every screen in §14.

---

## 6. Phased build (each phase fully detailed)

> Per-phase format: **Goal · Files · Build steps · API (live/mock) · States & gating · DoD.**
> Run the per-phase DoD in **both AR (rtl) and EN (ltr)** at **~360px and desktop** before moving on.

### Phase 0 — Contract + MSW handlers  *(contract ✅ done)*
**Goal:** a complete mock layer mirroring the §6 contract so any not-yet-live screen has a realistic backend.
- **Files:** `src/mocks/handlers.js`, `src/mocks/db.js` (in-memory seed: 1 merchant on trial, 2 cards,
  ~30 customers, staff, locations, invoices, campaigns, automations), `src/mocks/browser.js`,
  `public/mockServiceWorker.js` (via `npx msw init public/`).
- **Build steps:** install `msw` (dev). Implement a handler for **every §6 path**, returning contract-shaped
  JSON (snake_case, cursor pagination, `{error:{code,message,fields}}` on failures). Model the trial:
  `/me` returns `status:"trial"`, Growth-level entitlements. Make `PLAN_LIMIT` reproducible (e.g. set a low
  `max_cards` to test gating). Toggle MSW by `VITE_USE_MOCKS==="1"`.
- **API:** all mocked here; live paths (§4) can be left to the real backend by excluding their handlers when
  `VITE_API_URL` is set.
- **DoD:** every §6 path returns a realistic response under MSW; error + pagination shapes match the contract;
  toggling `VITE_USE_MOCKS` switches between mock and real cleanly.

### Phase 1 — Scaffold (spec §1–§9)  *(START HERE)*
**Goal:** the app boots with the Direction-C shell, RTL/i18n, auth guard, routing, and the API/mock layer
wired — no feature screens yet, just the skeleton every later phase plugs into.
- **Files:**
  - root: `package.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `index.html`
    (Google Fonts: Space Grotesk, Inter, Cairo, IBM Plex Mono), `.env.example`, `.eslintrc`, `.prettierrc`.
  - `src/main.jsx` — providers: `QueryClientProvider`, `BrowserRouter`, `I18nextProvider`, `ToastProvider`;
    conditional MSW start.
  - `src/App.jsx` — route table (§9) inside `Shell`.
  - `src/lib/api.js` — axios instance (`baseURL=VITE_API_URL+"/api/v1"`), request interceptor (Bearer),
    response interceptor (401→`/auth/refresh` once→retry→else `logout`), error mapping (`fields`→form,
    `message`→toast, `PLAN_LIMIT`→open UpgradeDrawer).
  - `src/lib/queryClient.js`, `src/lib/auth.js` (access in memory, refresh in `localStorage:kasbana_refresh`;
    `login()`→`/auth/token`→`/me` cache; `logout()` clears + redirects), `src/lib/i18n.js` (i18next init,
    `lng` from `localStorage:kasbana_lang` default `ar`, set `lang`+`dir` on change), `src/lib/format.js`
    (`arDigits`, EGP money, relative time via dayjs).
  - `src/locales/ar.json` + `en.json` — seeded with shell/nav/common keys (ar = source of truth).
  - `src/hooks/useAuth.js`, `src/hooks/useToast.js`, `src/hooks/usePlan.js` (stub returning `/me` entitlements).
  - `src/layout/Shell.jsx`, `Sidebar.jsx` (Overview, Cards, Customers, Analytics, Messaging, Locations, Team,
    Billing, Settings — lucide icons; bottom nav < md), `Topbar.jsx` (logo+name, ع/EN toggle, trial-countdown
    chip when `status==="trial"`, account menu), `RequireAuth.jsx` (no session → `/login?next=`).
  - `src/index.css` (Tailwind layers + base RTL).
- **Build steps:** create the Vite React app at `frontend/dashboard`; install deps (§1 list);
  paste §2 tokens into `tailwind.config.js`; wire fonts; implement `lib/`; seed `locales/`; build the
  Shell/Sidebar/Topbar to the Direction-C identity; wire routing (§9) with placeholder route elements;
  wire the Phase-0 MSW layer. Render a trial **Banner** above content when trialing and a **soft-lock
  overlay** (data visible, actions disabled, "Choose a plan" CTA) when the trial expired and plan is still trial.
- **API:** `GET /me` (live), `POST /auth/token|refresh` (live).
- **States & gating:** protected routes redirect to `/login`; trial banner + countdown show when trialing;
  `usePlan()` reads entitlements (drives later gating).
- **DoD:** app boots; Direction-C shell renders; ع/EN toggle flips `dir`/fonts/Arabic-Indic digits; protected
  routes redirect; trial banner + chip show for `status==="trial"`; `npm run lint` clean; `npm run build` ok.

### Phase 2 — Design system + primitives (spec §10–§13)
**Goal:** every reusable component exists, accessible + RTL-safe + bilingual, verified in a gallery.
- **Files:** `src/components/` — Button, Input, Select, Textarea, Toggle, Checkbox, Table, Modal, Drawer,
  Toast, Tabs, Badge, **KpiTile** (Direction-C `block`/`num`/`chip` variants), ColorPicker, FileUpload,
  DateRange, Stepper, EmptyState, Skeleton, Banner, **UpgradeDrawer**, QrBlock, **WalletPreview**,
  ChartLine, ChartBar, ChartDonut. Plus `src/routes/Gallery.jsx` at dev route `/__gallery`.
- **Build steps:** implement each per the §10 prop contracts (e.g. `Button{variant,size,loading,disabled,
  iconStart,onClick}`, `Table{columns,rows,loading,emptyState,onRowClick,pagination}` with Skeleton rows +
  card-stack < md, `Drawer` slides from inline-end). **WalletPreview (§11):** Apple `storeCard` (~340×210)
  + Google loyalty-object styles, parent-controlled Apple⇄Google toggle, live on prop change, LTR+RTL.
  **usePlan (§12):** `{plan, can(feature), limit(key), usage(key), atLimit(key)}`; gated control = lock icon
  + opens UpgradeDrawer (never hidden); over-limit create buttons disabled→drawer; server `PLAN_LIMIT`→drawer.
- **API:** none (FileUpload posts `/uploads` — mock until 1.6).
- **States & gating:** charts use token colors; global patterns (§13): Skeleton loading, EmptyState, error
  boundary, confirm Modal, optimistic toggles.
- **DoD:** every component renders accessible (labels/focus/keyboard), RTL-safe, in AR+EN; gating opens the
  UpgradeDrawer (never hides); WalletPreview updates live; `/__gallery` shows them all.

### Phase 3 — Auth + Onboarding (spec §14)  *(backend live)*
**Goal:** a merchant can sign up (start trial), log in, recover access, accept an invite, and onboard.
- **Files:** `src/features/auth/` Login, Signup, Forgot, Reset, Invite; `src/features/onboarding/Onboarding`.
- **Build steps & screens:**
  - **Login** `/login`: email, password, remember → `auth.login`; `UNAUTHENTICATED`→"wrong email/password";
    links to forgot/signup; `?next` redirect.
  - **Signup** `/signup`: rhf+zod (business_name, owner_name, email, phone EG, password ≥8, consent required
    PDPL) → `POST /auth/signup` → save tokens → `/onboarding`. Duplicate email = field error (409).
  - **Forgot** `/forgot` → `POST /auth/forgot` (always success msg). **Reset** `/reset/:token`: password+confirm
    → `POST /auth/reset` → `/login`; invalid/expired (410) shows clear message.
  - **Invite** `/invite/:token`: `GET /auth/invite/:token` shows merchant+role; set password →
    `POST /auth/invite/:token` → logged in; expired handled.
  - **Onboarding** `/onboarding`: 3-step Stepper — (1) branding (logo FileUpload, color_bg, color_fg →
    `PATCH /settings/business`); (2) first card (name, stamps_required 1–30, reward_title → `POST /cards`
    ACTIVE); (3) done (`QrBlock` from `/cards/:id/qr` + WalletPreview). Skippable/resumable.
- **API:** signup/forgot/reset/invite, `/me`, `PATCH /settings/business`, `POST /cards` — **all live**;
  `POST /uploads` + `/cards/:id/qr` mock (1.6).
- **States & gating:** none plan-gated; trial starts on signup.
- **DoD:** each screen's §14 acceptance criteria pass; signup→trial; refresh keeps session; completing
  onboarding leaves one ACTIVE card + QR; skipping → "Finish setup" tile flag for Overview.

### Phase 4 — Cards (spec §14)  *(designer/list/detail live; stats/qr mock)*
**Goal:** full stamp-card lifecycle — list, design (live preview), detail stats, enrollment QR.
- **Files:** `src/features/cards/` CardsList, CardDesigner, CardDetail, EnrollQr.
- **Build steps & screens:**
  - **CardsList** `/cards`: grid (mini WalletPreview, name, status Badge, holders, stamps_issued);
    "New card"→`/cards/new`, **disabled at `atLimit('max_cards')`** (UpgradeDrawer); row actions open/edit/
    duplicate/archive (confirm); empty → "Create your first card".
  - **CardDesigner** `/cards/new`, `/cards/:id/edit`: two-pane (left rhf+zod form, right **live WalletPreview**
    Apple⇄Google). Fields: name, stamps_required (slider+number 1–30), reward_title, reward_description, logo
    (FileUpload), color_bg/color_fg (ColorPicker, default merchant brand), collect-birthday toggle. Save draft
    (`DRAFT`) / Publish (`ACTIVE`) → `POST /cards` or `PATCH /cards/:id`; unsaved-changes guard; editing a
    published card warns it re-provisions holders' passes.
  - **CardDetail** `/cards/:id`: WalletPreview; stat KpiTiles (holders, stamps_issued, rewards_redeemed,
    completion_rate, Apple/Google donut from `/cards/:id/stats`); link to QR; edit/duplicate/archive.
  - **EnrollQr** `/cards/:id/qr`: big QrBlock (download PNG/SVG), copy join_url, "Download poster"
    (poster_pdf_url), **WhatsApp share** (`https://wa.me/?text=`), embed snippet.
- **API:** `/cards` list/create, `/cards/:id` get/patch — **live**; `/cards/:id/stats`, `/cards/:id/qr`,
  `/uploads` — **mock (1.6)**.
- **States & gating:** `atLimit('max_cards')` disables create + opens UpgradeDrawer; archive confirms.
- **DoD:** §14 Cards acceptance — preview mirrors form (both platforms); publish creates/updates ACTIVE;
  limit → drawer; QR → join_url; downloads + WhatsApp prefill work.

### Phase 5 — Overview + Customers + Analytics (spec §14)
**Goal:** the data home screen, customer management, and analytics.
- **Files:** `src/features/overview/Overview`, `src/features/customers/` CustomersList, CustomerProfile,
  `src/features/analytics/Analytics`.
- **Build steps & screens:**
  - **Overview** `/`: trial Banner; KpiTiles (active customers, stamps this week, rewards redeemed, new joins
    — each `deltaPct` vs previous period); 14-day ChartLine (metric switch); activity feed; quick actions
    (Share QR, New campaign, View customers); "Finish setup" tile if onboarding incomplete.
  - **CustomersList** `/customers`: debounced search; filter chips (card, status, segment lapsed>30d /
    reward-ready, location); Table `[name,phone,card,stamps X/N,last visit,joined,wallet]` (cursor pagination,
    row→profile); bulk-select; **Export CSV gated by `can('export')`**; empty → "Share your join QR".
  - **CustomerProfile** `/customers/:id`: header (name, phone, wallet Badge, joined, birthday); stamp progress
    + reward-ready Badge; **timeline** (enroll/stamp w/ staff+location+GPS/redeem/message); actions add/remove
    stamp (`/loyalty/stamp` ±1, respect `COOLDOWN_ACTIVE`→toast), mark redeemed (`/loyalty/redeem`), send
    message (Modal channel+text → `/customers/:id/message`); Data&privacy delete (confirm → `DELETE /customers/:id`).
  - **Analytics** `/analytics`: DateRange + location filter; charts joins (ChartLine), stamps/redemptions
    (ChartBar), retention curve (ChartLine), repeat+at-risk (KpiTiles), Apple/Google (ChartDonut), by-location
    (ChartBar); export. **Gating:** Starter (`features.analytics==='basic'`) → summary KPIs + joins only,
    rest locked (UpgradeDrawer); export gated.
- **API:** `/analytics/summary`, `/customers` list, `/loyalty/stamp|redeem` — **live**; `/analytics/timeseries|
  retention|by_location`, `/activity`, `/customers/:id`, `/customers/:id/timeline`, `/customers/:id/message`,
  `DELETE /customers/:id` — **mock** (timeseries/retention/by_location/activity/customer-detail = 1.6;
  message = 1.7).
- **States & gating:** export + advanced analytics gated; manual stamp optimistic with rollback.
- **DoD:** §14 acceptance — KPIs/chart/feed live with deltas + fresh-account empty state; filters/search/
  pagination work; timeline chronological; manual actions optimistic; delete confirms; Starter sees basic view.

### Phase 6 — Campaigns + Automations (spec §14)  *(mock until 1.7)*
**Goal:** outbound messaging — campaigns and lifecycle automations, with WhatsApp gating + allowance.
- **Files:** `src/features/campaigns/` CampaignsList, CampaignCompose, Automations.
- **Build steps & screens:**
  - **CampaignsList** `/campaigns`: Table (channel, audience, status, sent_at, delivered/opened).
  - **CampaignCompose** `/campaigns/new`: channel (PUSH/WHATSAPP/BOTH) → audience (`/segments`: all, lapsed,
    reward-ready, by card/location) → message (textarea AR/EN + preview) → send now/schedule → `POST /campaigns`.
    Show remaining WhatsApp allowance (`entitlements.usage`); WhatsApp & `!can('whatsapp')` or quota exhausted
    → block + UpgradeDrawer.
  - **Automations** `/automations`: 5 rows (reward_ready, expiry, birthday, winback, welcome) each Toggle +
    config (channel, timing, template) → `PATCH /automations/:key`; gate enabled count by `features.automations`.
- **API:** `/campaigns`, `/segments`, `/automations` — **mock (1.7)**.
- **States & gating:** WhatsApp capability + allowance enforced; automation count gated; both → UpgradeDrawer.
- **DoD:** §14 acceptance — push sends; WhatsApp gating+allowance enforced; scheduled shows scheduled; toggling
  persists; exceeding automation count opens drawer.

### Phase 7 — Locations + Team + Billing + Settings (spec §14)
**Goal:** org configuration + subscription management.
- **Files:** `src/features/locations/` LocationsList, LocationDetail; `src/features/team/Team`;
  `src/features/billing/Billing`; `src/features/settings/Settings`.
- **Build steps & screens:**
  - **Locations** `/locations` (+`/locations/:id`): Table `[name,address,staff_count,stamps_issued]`; "Add"
    Modal (name, address, lat/lng) → `POST /locations`, **disabled at `atLimit('max_locations')`**; detail
    edit (`PATCH /locations/:id`), map pin, per-location KpiTiles (`/locations/:id/stats`), assigned staff.
  - **Team** `/team`: Table `[name,role,location,status]`; "Invite" Modal (email, role, location) →
    `POST /staff/invite`, **disabled at `atLimit('max_staff')`**; row change role/location (`PATCH /staff/:id`),
    deactivate; **last-Owner protection** (disable + tooltip).
  - **Billing** `/billing`: current plan + trial countdown; plan comparison (Starter/Growth/Chain EGP prices,
    feature matrix, current highlighted); Upgrade/Downgrade → `POST /billing/subscribe` → redirect
    `checkout_url`; usage bars vs limits; payment method; invoices Table (date, amount, status, pdf_url);
    Cancel (confirm + reason → `/billing/cancel`); downgrade-exceeding-limits warns first.
  - **Settings** `/settings` (Tabs): Business (`PATCH /settings/business`); Branding (defaults); Notifications
    (owner email/WhatsApp → `PATCH /settings/account`); Language (AR/EN, writes `kasbana_lang`); Data&privacy
    (export, retention, request deletion); Account (change password `/settings/account/password`, sessions,
    delete account).
- **API:** `/locations` list/create, `/staff` list, `/settings/*` — **live**; `PATCH /locations/:id`,
  `/locations/:id/stats`, `POST /staff/invite`, `PATCH /staff/:id` — **mock (1.6)**; all `/billing/*` — **mock (1.7)**.
- **States & gating:** create gated at limits; downgrade warning; last-Owner protected.
- **DoD:** §14 acceptance — add gated at limit; edits persist; plan + trial correct; subscribe → checkout;
  usage bars match; invoices download; each settings tab saves immediately; language toggle flips `dir`.

### Phase 8 — QA gate (spec §16) on every screen
**Goal:** ship-quality across the whole app + final integration of the mock-only screens.
- **Checklist (every screen):** AR+EN correct · responsive 360px + desktop · all states (loading/empty/error/
  gated/over-limit/success) · gating via `usePlan` · no hardcoded strings · logical CSS only · requests match
  §6 · keyboard + screen-reader a11y · EGP money · `npm run lint` clean.
- **Integration:** point `VITE_API_URL` at staging, disable MSW; the 1.0–1.5 screens should already be real,
  so this confirms the 1.6/1.7-backed screens as those endpoints land. Any mismatch is fixed in the backend
  to match the contract.
- **DoD:** §16 passes on every screen against the real backend (or MSW for any still-pending endpoint).

---

## 7. Verification

- **Per phase:** `npm run dev` in `frontend/dashboard`; check the phase's screens against their §14
  acceptance criteria in **both AR (rtl) and EN (ltr)** at **~360px and desktop**; `npm run lint`; exercise
  live endpoints against the real backend and pending ones against MSW.
- **Visual fidelity:** each screen matches the Direction-C identity (dark ink sidebar/chart, colored KPI
  blocks, mono Arabic-Indic numbers, `shadow-bold`, amber primary).
- **Integration (incremental):** live-endpoint screens integrate as built; 1.6/1.7 screens flip per-path as
  endpoints land on staging. The contract is the agreed source of truth.

## 8. Open decisions
1. **App is standalone** — decided: the dashboard is its own independent app sharing nothing with the
   marketing app; the marketing app is not touched or restructured.
2. **Deploy target** — decided: **subdomain** `app.kasbana.net` (dashboard at its root, bare routes;
   marketing's "Login" links out to it). Own build, independent of marketing's `distribute.yml`. Flag the
   DNS + deploy to infra.
3. **Plan-gating numbers** (§15) — confirm real Starter/Growth/Chain limits with pricing; the backend's
   `billing/plans.py` holds the source values, the frontend reads them from `/me` entitlements.
4. **Contract additions** (§4/§0) — ✅ done: §6 endpoints in `openapi.yaml` (`x-status: dashboard-proposed`);
   backend implementing (1.0–1.5 live; 1.6/1.7 in progress).
5. **`birthday` field** — the customer screens surface `birthday`; it depends on the one backend joint-PR
   (`CustomerCard.birthday`), so keep it mock-backed until 1.6 lands it.
