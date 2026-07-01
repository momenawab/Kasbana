# Stampn — Platform Admin Panel — Implementation Plan

> Created **2026-07-01**. A **new, separate application** for the Stampn team to
> operate the whole platform: manage subscribers (merchants), billing, support,
> analytics, and configuration. This is **not** the merchant dashboard
> (`app.stampn.net`) — it is the internal back-office at **`admin.stampn.net`**.
>
> 15 phases, backend + frontend, each independently shippable. Read the
> **Architecture** and **Cross-cutting** sections first — they apply to every phase.

---

## 0. What this is (and is not)

| | Merchant Dashboard (`app.stampn.net`) | **Admin Panel (`admin.stampn.net`)** |
|---|---|---|
| Users | A coffee shop's staff (Owner/Admin/Marketing/Designer/Scanner) | **Stampn employees** (Super-admin/Finance/Support/…) |
| Data scope | Their own merchant only (tenant-scoped) | **All merchants** (cross-tenant, deliberately) |
| Auth | Merchant `User`/`StaffUser` JWT | **Separate `AdminUser` JWT** (different audience) |
| Purpose | Run one loyalty program | Run the whole SaaS business |
| Risk profile | Medium | **Highest** — full cross-tenant + billing + impersonation |

The admin panel is the **highest-value attack target in the system.** Security
is not a phase — it threads through every one (see Cross-cutting §Security).

---

## 1. Architecture & foundational decisions

### Naming (fixed for the whole project)
| Thing | Value |
|---|---|
| Backend Django app | **`console`** (can't be `admin` — Django reserves it) |
| Admin user model | `console.AdminUser` |
| API URL prefix | **`/api/admin/v1/…`** (separate from merchant `/api/v1/…`) |
| Frontend app | **`frontend/admin`** (mirrors `frontend/dashboard`) |
| Public domain | **`admin.stampn.net`** (already reserved in the rebrand) |
| Deploy branch | **`deployment-admin`** (Hostinger serves it) |
| CI workflow | **`deploy-admin.yml`** (gated on `prod`, lockstep with backend) |

### Separate authentication boundary (critical)
- `AdminUser` is a **standalone model**, unrelated to merchant `User`/`StaffUser`.
- Admin JWTs carry a distinct **`aud: "admin"`** claim (or a separate signing
  key). A merchant token must **never** authenticate an admin endpoint, and an
  admin token must never pass merchant auth. Enforced by a custom
  `AdminJWTAuthentication` + `IsAdminUser` permission on every admin view.
- Admin login is its own endpoint (`/api/admin/v1/auth/login`), **MFA-required**.

### Cross-tenant access (controlled inversion)
- Every merchant-side queryset uses `for_merchant`/`TenantManager` scoping. Admin
  views **deliberately bypass** that to see all merchants. This inversion is
  centralised in a base `AdminAPIView` (auth + audit + role gate) so no admin
  view forgets the guards.

### Config in the DB, not code (enabler for Phase 3–4)
- Today `PLAN_LIMITS` / `PLAN_PRICES_EGP` are **hardcoded** in `billing/plans.py`.
  To let admins edit plans/prices without a deploy, Phase 3 introduces a **`Plan`
  model** and migrates the config into it (with the hardcoded map as the seed +
  fallback). This is the single biggest structural change.

### Deployment topology
```
dev  →  promote to prod  →  deploy-admin.yml (on prod, lockstep)
                              builds frontend/admin  →  deployment-admin branch
                              →  Hostinger serves admin.stampn.net
backend /api/admin/v1  ships in the SAME backend image (no new service)
```
Defence-in-depth: put **IP allowlist / basic-auth at Caddy** in front of
`admin.stampn.net` on top of app-level auth.

---

## 2. Tech stack (reuse the dashboard's)
- **Backend**: Django + DRF + SimpleJWT (new auth class), PostgreSQL, Celery,
  same image. New app `console`. Same gates: ruff/black/mypy/pytest/spectacular.
- **Frontend**: React + Vite + Tailwind + React Query + react-router (identical
  to `frontend/dashboard`). **English-only is acceptable** (internal tool) — skip
  the ar/en i18n effort unless the team wants it.
- **Charts**: recharts (already used). **Tables**: reuse the dashboard `Table`.

---

## 3. Cross-cutting concerns (apply to ALL phases)

### Security (every phase)
- `AdminUser` separate auth boundary + `aud:"admin"`; MFA (TOTP) from Phase 1
  scaffold, enforced by Phase 15.
- **Least privilege**: admin roles gate mutations (view ≠ refund ≠ delete).
- **Audit everything**: every mutation writes an `AdminAuditLog` row (actor, action,
  target, before/after, IP, UA, at). Read of sensitive data (impersonation, PII
  export) is logged too.
- Admin API **rate-limited**; IP allowlist at the edge; short JWT lifetimes.
- No admin endpoint is reachable from the merchant API surface (separate router).

### Audit log (foundational — built in Phase 1, viewer in Phase 13)
`AdminAuditLog(actor_admin, action, target_type, target_id, metadata_json,
ip, user_agent, created_at)`. A DRF mixin/decorator auto-logs mutating actions.

### Testing & quality (every phase)
- Backend: pytest per feature (auth boundary, cross-tenant access control,
  audit-write, permission matrix). Keep ruff/black/mypy/spectacular clean.
- Frontend: lint + build clean. Component-level where it matters.
- **Security tests are mandatory**: prove a merchant token is rejected by admin
  endpoints, and a low-role admin is 403'd on high-privilege actions.

### Data model additions (summary — created across phases)
| Model | Phase | Purpose |
|---|---|---|
| `AdminUser`, `AdminAuditLog` | 1 | Auth + audit |
| Merchant admin fields (`suspended`, `internal_notes`, `flags`, `account_manager`, `health_score`) | 2/9 | Ops metadata |
| `Plan` (+ features/limits/price) | 3 | DB-backed plan catalogue |
| Subscription admin fields (`comp`, `override_plan`, `override_expires`) | 4 | Manual control |
| `Refund` / invoice actions | 5 | Billing ops |
| `SupportNote`, `Impersonation` | 6 | Support |
| `Announcement` | 10 | Broadcasts |
| `Coupon` / `Promotion` | 11 | Discounts |
| `AdminRole`/permission map | 12 | Admin RBAC |
| `FeatureFlag`, `PlatformSetting` | 14 | Config |

---

# The 15 Phases

Each: **Goal · Backend · Frontend · Security · Depends on · DoD**.

---

## Phase 1 — Foundation, Admin Auth & Audit Core — ✅ DONE
**Goal:** a logged-in admin sees an empty shell at `admin.stampn.net`; the auth
boundary, audit spine, and deploy pipeline exist.

**Shipped:** `console` app with `AdminUser` (standalone, hashed pw, role) +
`AdminAuditLog` + `audit.record()`; `AdminJWTAuthentication` (custom `realm:"admin"`
claim — merchant tokens rejected, and vice-versa, proven by tests), `IsAdminUser`/
`IsSuperAdmin`/`HasAdminRole` + base `AdminAPIView`; `POST /api/admin/v1/auth/login`
(audited, throttled `admin_auth` 10/min) + `/auth/refresh` + `GET /me`;
`createadmin` command. Frontend `frontend/admin` (Vite/Tailwind/RQ, dark theme,
port 5175): login, auth guard, `AdminShell` with the full nav map, Overview home.
`deploy-admin.yml` (prod→`deployment-admin`) + CORS for `admin.stampn.net`.
9 boundary tests; 218 backend tests green; FE lint+build clean.

**Backend**
- New app `console`. `AdminUser` model (email, password, name, role FK/enum,
  is_active, mfa_secret, last_login_ip). `AdminAuditLog` model + `audit()` writer
  + DRF mixin for auto-logging mutations.
- `AdminJWTAuthentication` (checks `aud:"admin"`), `IsAdminUser` +
  `IsSuperAdmin` permissions, base `AdminAPIView`.
- Endpoints: `POST /api/admin/v1/auth/login` (email+password → admin JWT; MFA
  challenge scaffold), `/auth/refresh`, `GET /api/admin/v1/me`.
- URL router mounted separately in `config/urls.py`; NOT under `/api/v1/`.
- `manage.py createadmin` command to seed the first super-admin.

**Frontend**
- Scaffold `frontend/admin` (Vite/Tailwind/RQ/router, its own `package.json`).
- Login screen, auth guard, `AdminShell` (sidebar + topbar), `/me` bootstrap,
  logout, dark professional theme.
- `lib/api.js` pointed at `/api/admin/v1`, admin-token storage (separate key).

**Security**
- Separate signing/`aud`; MFA fields present (enforcement deferred to 15);
  audit-write on login; admin token key namespaced so it can't collide with the
  merchant dashboard on a shared browser.

**Depends on:** nothing. **DoD:** admin logs in, sees an empty shell live on
`admin.stampn.net`; merchant JWT is rejected by admin endpoints (test); deploy
pipeline (`deploy-admin.yml` + `deployment-admin` branch) green.

---

## Phase 2 — Merchant Directory (list + 360° detail) — ✅ DONE
**Goal:** find any merchant and see everything about them (read-only).

**Shipped:** `GET /api/admin/v1/merchants` (cross-tenant, `q`/`status`/`plan`
filters, cursor-paginated, annotated cards/customers/staff/locations counts) +
`GET /merchants/{id}` 360° (profile, subscription snapshot, owner+contact, usage,
Apple/Google wallet counts, admin_meta). Admin-only data kept OUT of frozen core
via a `console.MerchantAdminMeta` sidecar (notes/flags/account_manager; migration
0002). Frontend Merchants list (searchable/filterable table) + detail (header +
tabbed Overview, later-phase placeholders). 7 tests incl. the security check that
a merchant token can't reach the cross-tenant directory. 225 backend tests green.

**Backend**
- `GET /api/admin/v1/merchants` — cross-tenant list: search (name/slug/email/
  phone), filter (status, plan, trial/active/locked, created range), sort,
  cursor-paginated. Annotate counts (cards, customers, staff, locations).
- `GET /api/admin/v1/merchants/{id}` — 360° detail: profile, plan/subscription
  snapshot, usage vs limits, owner contact, created/last-active, wallet pass
  counts, recent activity.
- Admin-only `Merchant` fields added (migration): `internal_notes` (stub),
  `flags` (JSON), `account_manager` (FK AdminUser, nullable).

**Frontend**
- **Merchants** list: searchable/filterable table, status/plan badges, quick
  stats columns. Row → detail.
- **Merchant detail**: header (name, plan, status, MRR), tabbed sections
  (Overview · Subscription · Billing · Usage · Activity) — most tabs are
  placeholders filled by later phases.

**Security**
- All queries via `AdminAPIView` (audited read of PII). Role: any admin can view;
  notes/flags edit gated to Support+.

**Depends on:** 1. **DoD:** every merchant is findable; detail shows accurate
cross-tenant data; PII reads audited.

---

## Phase 3 — Plan Catalogue Management (DB-backed plans) — ✅ DONE
**Goal:** admins create/edit plans, limits, features, and prices without a deploy.

**Shipped:** `billing.Plan` model (key/name/price_egp/is_public/archived + the
full limit/feature set) + a seed migration loading the four tiers from
`PLAN_LIMITS`/`PLAN_PRICES_EGP`. A single cached catalogue (`_catalogue()`, 60s,
invalidated on every admin write) backs three DB-backed accessors — with the
hardcoded maps as fallback: `plan_limits_map()` (entitlements + messaging quota/
automations) and `plan_price()` (what **subscribe/checkout actually charges** +
the merchant billing page), so a price/limit edit takes effect live. Every
reader was migrated off the hardcoded constants: `entitlements.check`/`describe`,
`messaging.metering.quota_for`, `messaging.views` automation gate, and
`billing.views` subscribe/state. Archived plans stay in resolution (archiving
only hides them from the catalogue *listing*). `GET/POST /api/admin/v1/plans` +
`GET/PATCH /plans/{key}` (archive is `PATCH {"archived": true}`, not delete);
mutations gated to Super-admin/Finance via a new `IsFinanceAdmin` permission,
reads open to any admin; every create/update/archive audited with before/after.
Frontend **Plans** screen (table + inline create/edit form), role-gated Actions
column. 16 new backend tests (boundary + role gate + CRUD + audit + live
entitlements + live checkout price + archived-plan resolution); 233 backend
tests green; ruff/black/mypy/spectacular clean. Verified live in-browser (list,
edit, role-gated read-only view). **Deferred:** "draft vs published" staged
edits — not needed for the DoD and adds real workflow complexity; edits apply
immediately today, same as every other admin mutation in this panel.

**Backend**
- New `Plan` model: `key`, `name`, `price_egp`, `is_public`, and the limit/feature
  fields (`max_cards/locations/staff/customers`, `whatsapp`, `export`, `api`,
  `specialized_roles`, `custom_branding`, `automations`, `analytics`,
  `whatsapp_quota`). Migrate `PLAN_LIMITS`/`PLAN_PRICES_EGP` → seed data; keep the
  hardcoded map as fallback if the table is empty.
- Refactor `billing/entitlements.py` + `billing/plans.py` to read from `Plan`
  (cached). **Careful, high-blast-radius refactor** — full regression run.
- Endpoints: `GET/POST /api/admin/v1/plans`, `GET/PATCH /plans/{key}`,
  archive (not delete — keep for historical subscriptions).

**Frontend**
- **Plans** screen: table of plans; editor form (limits, feature toggles, price,
  visibility). "Draft vs published" so edits don't take effect mid-review.

**Security:** plan edits are high-impact → gated to **Super-admin/Finance**;
every change audited with before/after.

**Depends on:** 1, 2. **DoD:** entitlements read from DB; editing a plan changes
gating live; existing subscriptions unaffected; all billing/entitlement tests green.

---

## Phase 4 — Subscription Management — ✅ DONE
**Goal:** operate any merchant's subscription: change plan, extend trial, comp,
lock/unlock, override.

**Shipped:** `Subscription` gains `comp`/`override_plan`/`override_expires_at`/
`notes`; `effective_plan()` resolves override (if active) → comp → normal
trial/paid/locked logic, so override always wins (even over a lock, for
emergency unblocks) and comp bypasses billing status entirely. `billing.services`
gains `unlock`/`extend_trial`/`set_comp`. `GET/PATCH /merchants/{id}/subscription`
(PATCH sets plan/status/override/notes, requires `reason`, blocks a downgrade
with a `409 PLAN_DOWNGRADE_BLOCKED` + per-capability shortfall unless
`force: true`) + `POST .../extend-trial`, `.../comp`, `.../lock`, `.../unlock`
+ `GET .../audit` (last 20 subscription changes). Mutations gated to
Super-admin/Finance (reads open to any admin); every action audited with
before/after. Frontend Subscription tab: state badges (incl. live effective
plan), the plan/status/override/notes form, three quick-action cards
(extend-trial, comp, lock/unlock — the last relabels itself live), and the
audit trail — all read-only for non-Finance roles. 22 new backend tests
(role gate, PATCH incl. guardrail forced/blocked, extend-trial, comp-bypasses-lock,
lock/unlock round-trip, override-beats-lock, expired-override-falls-back, audit
trail); 255 backend tests green; ruff/black/mypy/spectacular clean. Verified
live in-browser: locked a merchant, comp'd it back to access, extended its
trial (which also un-locks, since extend-trial always sets TRIALING), watched
the audit trail update after each action, and confirmed the Support role sees
state + audit only, no controls.

**Backend**
- Subscription admin fields (migration): `comp` (free access), `override_plan`,
  `override_expires_at`, `notes`.
- Endpoints (all audited): `PATCH /merchants/{id}/subscription` (set plan,
  status), `POST …/extend-trial {days}`, `POST …/comp {on,reason}`,
  `POST …/lock` / `…/unlock`, and safe reuse of `billing.services`.
- Guardrails: can't silently drop a paying merchant below their usage; warn on
  downgrade that would break limits.

**Frontend**
- Merchant detail → **Subscription** tab: current state, change-plan, extend-trial,
  comp toggle, lock/unlock, with reason prompts and a confirmation for destructive
  ones. Shows the audit trail of subscription changes inline.

**Security:** billing-impacting → **Finance/Super-admin**; reason required;
audited.

**Depends on:** 3. **DoD:** admin can move a merchant trial→paid→comp→locked and
it reflects in the merchant's live entitlements; every action audited.

---

## Phase 5 — Billing, Invoices & Payments — ✅ DONE (no-refund scope)
**Goal:** full visibility + control over money: invoices, payments, dunning.

**Scope note:** refunds are **not a feature of this system** (confirmed — there's
no refund initiation capability anywhere; a Paymob-side refund only ever
surfaces passively as a `canceled` webhook event, handled since Phase 1.4).
Dropped the `Refund` model, the refund endpoint, and the Paymob refund API call
from this phase entirely — everything else shipped.

**Shipped:** `GET /api/admin/v1/invoices` (cross-tenant, status/merchant_id/
date-range filters, cursor-paginated) + `GET /invoices/{id}`. `POST
/invoices/{id}/retry` — FAILED-only (409 `INVOICE_NOT_FAILED` otherwise), a
fresh gateway checkout at the merchant's **current** plan/price (prefers
`pending_plan` over `plan` so a first-subscribe failure while still TRIALING
doesn't retry at FREE/0). `POST /merchants/{id}/invoices` — manual/one-off
invoice (`status="paid"` default = mark-paid for an offline payment,
`"pending"` = expected-not-yet-received); `Invoice.note` added (admin-only,
outside the frozen contract's Invoice shape). `GET /billing/dunning` — merchants
`PAST_DUE`; `apply_webhook_event`'s `failed` branch now flips an ACTIVE
merchant to `PAST_DUE` (a first-subscribe failure while TRIALING is untouched)
— the actual signal dunning needs. `POST /merchants/{id}/dunning/notify` —
emails the owner a reminder (`send_mail`, fail-silently). `GET
/billing/reconciliation` — internal consistency report (stale pending manual
invoices 7+ days old; ACTIVE-via-a-real-checkout subscriptions with zero PAID
invoices) — **not** a live Paymob transaction-log match, which needs Paymob's
reporting API/export and real credentials (out of scope, per this phase's own
dependency). Mutations gated to Super-admin/Finance, reads open to any admin,
every mutation audited. Frontend: global **Billing** page (Invoices · Dunning ·
Reconciliation tabs, hard-confirmed retry/notify) + a merchant-scoped Billing
tab (invoice history + the manual-invoice/mark-paid form) on the merchant
detail page. 24 new backend tests incl. the PAST_DUE webhook signal, the retry
pending-plan-vs-FREE trap, and the reconciliation exclusions; 277 backend
tests green; ruff/black/mypy/spectacular clean. Verified live in-browser:
cross-tenant invoice list/detail/retry, dunning list + notify (audited),
reconciliation flags, and the merchant-scoped mark-paid flow.

**Security:** manual invoices/retry/notify → **Finance/Super-admin**; audited.

**Depends on:** 4. **DoD:** an admin can retry a failed charge and record an
offline payment; dunning surfaces overdue merchants; reconciliation flags
internal data-integrity gaps.

---

## Phase 6 — Support Tools & Impersonation
**Goal:** resolve merchant tickets fast — see what they see, fix their account.

**Backend**
- **Impersonation**: `POST /merchants/{id}/impersonate` → a **short-lived, scoped
  merchant JWT** carrying `impersonated_by:<admin id>`; every impersonated action
  is tagged in both merchant + admin audit. `POST /impersonate/end`.
- Support actions (audited): reset merchant owner password / send reset,
  resend staff invite, unlock account, force-verify email, clear a stuck state.
- `SupportNote` model (merchant, admin, body) + per-merchant activity timeline
  (enroll/stamp/redeem/login/billing events, cross-sourced).

**Frontend**
- Merchant detail → **Support** tab: "View as merchant" button (opens the
  merchant dashboard in an impersonation session with a persistent "You are
  viewing as {merchant} — exit" banner), support actions, notes thread, activity
  timeline.

**Security:** impersonation is the sharpest tool — **time-limited, fully audited,
banner-flagged, Support+ only, never for billing actions**; merchant dashboard
shows the impersonation banner.

**Depends on:** 2. **DoD:** admin can view-as a merchant, fix common issues, and
leave notes; every impersonated action is attributable to the admin.

---

## Phase 7 — Revenue & Financial Analytics
**Goal:** know the health of the business at a glance.

**Backend**
- `GET /api/admin/v1/analytics/revenue`: **MRR, ARR, ARPU, LTV, churn rate
  (logo + revenue), trial→paid conversion, net revenue retention**, revenue by
  plan, new vs churned MRR, cohort retention. Date-ranged, cached.
- Export endpoints (CSV) for finance.

**Frontend**
- **Revenue** dashboard: KPI tiles (MRR/ARR/churn/conversion), MRR-movement chart
  (new/expansion/churned), revenue-by-plan breakdown, cohort retention heatmap,
  CSV export.

**Security:** financials → **Finance/Super-admin** (hidden from Support/read-only).

**Depends on:** 5. **DoD:** accurate MRR/churn/conversion vs the raw
subscription+invoice data; finance can export.

---

## Phase 8 — Platform Analytics & Usage
**Goal:** operational insight into how the platform is used (non-financial).

**Backend**
- `GET /api/admin/v1/analytics/platform`: total/active/trial/churned merchants,
  total customers/cards/stamps/redemptions across the platform, **wallet pass
  counts (Apple vs Google)**, **feature adoption** (% using referrals / points /
  automations / branded enroll / campaigns), growth over time, geographic/city
  distribution, top merchants by activity.

**Frontend**
- **Platform** dashboard: growth charts, feature-adoption bars, wallet split,
  activity leaderboards, funnel (signup → trial → active → paying).

**Security:** any admin may view (no PII beyond aggregates).

**Depends on:** 2. **DoD:** platform KPIs match raw counts; feature-adoption
informs the roadmap.

---

## Phase 9 — Merchant Lifecycle & Moderation
**Goal:** manage merchants through their lifecycle and keep the platform clean.

**Backend**
- **Lifecycle pipeline**: leads → trial → active → churned states; `Merchant`
  `health_score` + at-risk detection (low activity, trial ending, failed
  payment). Endpoints for the pipeline board + at-risk list.
- **Moderation**: suspend/ban a merchant (audited, with reason; blocks their
  API), a **flagged-content queue** (cards/branding/logos flagged by heuristics
  or reports) with approve/reject.
- Suspension propagates to the merchant API (their staff get a clear "account
  suspended" state).

**Frontend**
- **Lifecycle** board (kanban-ish by stage), **At-risk** list with reasons,
  **Moderation** queue (review flagged content, approve/reject/suspend).

**Security:** suspend/ban → **Super-admin**; moderation → Support+; all audited.

**Depends on:** 2, 6. **DoD:** at-risk merchants surface early; a bad actor can be
suspended and is immediately blocked; flagged content is reviewable.

---

## Phase 10 — Communications & Announcements
**Goal:** reach merchants — product news, outages, upgrade nudges.

**Backend**
- `Announcement` model (title, body, audience-segment, channel[in-app|email],
  schedule, status). Segments: all / by plan / trial-ending / at-risk / by
  activity. Endpoints CRUD + send/schedule; Celery send task; email via existing
  mail backend.
- In-app delivery: an endpoint the **merchant dashboard** reads to show a banner /
  notification center (small merchant-side addition).

**Frontend**
- **Announcements**: composer (title/body/audience/channel/schedule), list with
  status + reach/open stats, template library, **changelog/release-notes** publisher.

**Security:** broadcast is high-visibility → **Super-admin/Marketing-admin**;
audited; preview + confirm before send.

**Depends on:** 2, 8 (segments). **DoD:** an admin can broadcast to a merchant
segment (in-app + email) and see delivery stats.

---

## Phase 11 — Coupons, Discounts & Promotions
**Goal:** run growth levers — discounts, comps, trial extensions, partners.

**Backend**
- `Coupon` model (code, type[percent|fixed|free-months|trial-extension], value,
  plan-scope, max-redemptions, per-merchant, expiry, active). Applied at
  subscribe/checkout (Paymob) + admin-granted comps. `Promotion` grouping.
- Optional **partner/affiliate** tracking (who referred this merchant; payout
  report).
- Endpoints: CRUD coupons, redemption report, apply-to-merchant.

**Frontend**
- **Promotions**: coupon builder, active-codes table + redemption stats, apply-
  coupon-to-merchant action, partner/affiliate report.

**Security:** discounts affect revenue → **Finance/Super-admin**; audited;
redemption limits enforced server-side.

**Depends on:** 4, 5. **DoD:** a working discount code reduces a merchant's charge;
redemptions are capped and reported.

---

## Phase 12 — Admin Team & RBAC
**Goal:** safely delegate — multiple admins with scoped permissions.

**Backend**
- Admin roles: **Super-admin, Finance, Support, Marketing-admin, Read-only,
  Engineering** (extensible). Central **permission matrix** (which role may do
  what) enforced by permission classes across all admin endpoints (retrofit the
  gates added ad-hoc in earlier phases into one matrix).
- Endpoints: manage admin users (invite, deactivate, change role), list, audit of
  admin-user changes. MFA enforcement flag per role.

**Frontend**
- **Admin Team**: admin users table, invite, role assignment, deactivate, the
  permission matrix (read-only reference), per-admin activity.

**Security:** managing admins → **Super-admin only**; last-super-admin protection;
role changes audited; **MFA enforced for privileged roles**.

**Depends on:** 1 (+ all prior gates). **DoD:** a Support admin can't refund or edit
plans; a Read-only admin can't mutate anything; matrix is the single source of truth.

---

## Phase 13 — Audit Log Viewer & Compliance (PDPL)
**Goal:** answer "who did what?" and honor data-protection obligations.

**Backend**
- Audit **viewer** API: search/filter the `AdminAuditLog` by admin/action/target/
  date; export.
- **Compliance**: per-merchant **data export** (all their data as a bundle),
  **right-to-be-forgotten** = delete a merchant + full cascade (customers,
  cards, ledger, wallets) with a hard confirm + audit; consent-record view;
  data-retention policy settings.

**Frontend**
- **Audit Log** viewer (powerful filters, detail drawer with before/after).
- **Compliance** tools: export-merchant-data, delete-merchant (typed confirm),
  consent records, retention settings.

**Security:** delete-merchant → **Super-admin**, typed confirmation, irreversible,
heavily audited; exports audited (they contain PII).

**Depends on:** 1 (audit spine), 2. **DoD:** any admin action is traceable; a
merchant's data can be exported or fully deleted on request.

---

## Phase 14 — Platform Operations, Health & Config
**Goal:** run the machine — health, jobs, integrations, feature flags, settings.

**Backend**
- **Health**: API/DB/Redis/Celery status, queue depth, failed-task list
  (billing/messaging/wallets), **wallet provisioning failures** (Google/Apple
  sync errors), **Paymob webhook delivery log**, error-rate summary (Sentry link).
- **Feature flags**: `FeatureFlag` model — toggle features globally or per
  merchant (e.g. re-enable WhatsApp/Fawry, gate a beta). `PlatformSetting` for
  global config. **Maintenance mode** toggle.
- Endpoints for all of the above (read + toggle).

**Frontend**
- **Operations** dashboard: health tiles, job/queue monitor with retry, wallet-
  sync failures with re-provision action, webhook log, **Feature Flags** manager,
  **Settings** (global config, maintenance mode).

**Security:** flags/settings/maintenance → **Super-admin/Engineering**; retries
audited.

**Depends on:** 1. **DoD:** the team sees platform health at a glance, can retry
failed jobs / re-provision passes, and flip feature flags without a deploy.

---

## Phase 15 — Hardening, Security & Launch
**Goal:** make the admin panel production-safe and launch it.

**Scope**
- **MFA/2FA enforced** (TOTP) for all admins (mandatory for privileged roles).
- **IP allowlist / edge auth** at Caddy in front of `admin.stampn.net`.
- **Session management**: short JWT + refresh rotation, "log out everywhere",
  device/session list, forced re-auth for sensitive actions (refunds, delete).
- **Admin API rate limits** (stricter than merchant), brute-force lockout.
- **Admin-panel Sentry** (backend tag + frontend browser SDK).
- **Security review / pentest checklist**: cross-tenant leakage tests, auth-
  boundary tests, permission-matrix tests, impersonation-abuse tests, audit-
  completeness tests, dependency audit.
- **Backups/runbook**: admin data covered by the existing backup; incident runbook
  for a compromised admin account (rotate, revoke sessions, audit review).
- **Load test** the cross-tenant analytics queries; add indexes as needed.

**DoD:** MFA on for all admins; edge allowlist live; security test suite green;
Sentry live; launch checklist signed off.
docker compose -f infra/compose.prod.yml exec web python manage.py createadmin --email admin@stampn.net --role SUPER_ADMIN
---

## 4. Suggested MVP cut (if you want value fast)
If the team needs the panel sooner than 15 phases, the **operational MVP** is:
**Phases 1 → 2 → 4 → 5 → 6** (auth, merchant directory, subscription control,
billing, support+impersonation). That alone lets the team manage subscribers and
support them — the core of the request. Add 3 (DB plans) if you need to change
pricing without deploys. Everything else is high-value but sequential.

---

## 5. Open decisions to confirm
1. **App name** — proposed `console` for the backend Django app (since `admin` is
   reserved). OK, or prefer `backoffice`/`platform`?
2. **Language** — admin panel **English-only** (internal tool)? Recommended, saves
   the ar/en effort. Confirm.
3. **Plans in DB (Phase 3)** — this refactors the live entitlements engine. Do it
   early (flexible pricing) or defer and keep plans in code for now?
4. **Impersonation** — allow "view as merchant" at all? (Powerful for support, but
   the sharpest security tool.) Recommended **yes**, time-limited + audited.
5. **Edge protection** — IP allowlist for `admin.stampn.net`? Recommended for an
   internal tool; confirm the team has static IPs / VPN.

---

## 6. Cross-cutting checklist (per phase, before promote)
- [ ] Backend: models + migration, endpoints, `AdminAPIView` (auth+audit+role),
      tests (incl. auth-boundary + permission), ruff/black/mypy/spectacular clean.
- [ ] Frontend: screen(s), wired to `/api/admin/v1`, lint + build clean.
- [ ] Security: role gate correct; mutations audited; no cross-tenant leak.
- [ ] Docs: update this plan's checkboxes; note contract additions.
- [ ] Promote `dev → prod`; confirm `deploy-admin.yml` deploys `admin.stampn.net`.
