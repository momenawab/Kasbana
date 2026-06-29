# Stampn Backend — Remaining Phases & Tasks

> Status as of **2026-06-29** (branch `dev`; prod running image `f3de98bae4af`).
> The frozen `contracts/openapi.yaml` (v1.1.0) defines ~45 endpoints. Phases
> **1.0–1.5 + observability are done**; what remains is **1.6 (Dashboard
> completeness)**, **1.7 (Billing & Messaging)**, one small **core joint-PR**, and
> **1.8 (hardening)**. Each phase below lists Goal · New models · Endpoints ·
> Files · Tasks · Gating · Migration note · DoD.
>
> Conventions (all phases): snake_case JSON · EGP money (`*_egp`, major units) ·
> cursor pagination `{next,previous,results}` · error envelope
> `{error:{code,message,fields}}` · tenant-scope every queryset via
> `core.tenancy` · reuse `common.permissions`, `common.errors`,
> `billing.entitlements` · `ruff`+`black`+`mypy` clean · tests green ·
> `manage.py spectacular` 0 errors.

---

## ✅ Done

- **1.0 Foundation** — models, enums, constants, JWT auth, RBAC, tenancy,
  `core.ledger`, error envelope, OpenAPI, Celery.
- **1.1 Enrollment + Wallets** — `enroll/{token}`, Apple Wallet web service,
  Google provisioning, `wallets.service` façade + tasks.
- **1.2 Loyalty** — `POST /loyalty/stamp`, `POST /loyalty/redeem`,
  `GET /loyalty/cards/{id}` + anti-fraud (cooldown / velocity).
- **1.3 Dashboard CRUD** — `cards` (list/create/detail), `customers` (list),
  `staff` (list/create), `locations` (list/create), `analytics/summary`.
- **1.4 Entitlements + Trial** — `billing.Subscription`, `PLAN_LIMITS`,
  `check()`/`enforce()`, `expire_trials` beat task, dashboard create-gating.
- **1.5 Account & Session** — `accounts/` app: `auth/signup|forgot|reset|invite`,
  `GET /me`, `settings/business|account|account/password`; models `StaffInvite`,
  `PasswordResetToken`, `MerchantSettings`; `billing/wire.py` enum mapping.
- **Observability** — Sentry wired (errors + Celery + log forwarding, release =
  deploy SHA); **live in prod**.

---

## ⬜ Core joint-PR (do before 1.6) — `CustomerCard.birthday`

The only frozen-`core/` change. Coordinate with Joe.
- **Task:** add `birthday = models.DateField(null=True, blank=True)` to
  `core.models.CustomerCard`; single `core/` migration; update the contract note.
- **Why:** consumed by 1.6 (`GET /customers/{id}` returns `birthday`) and 1.7
  (the `birthday` automation). Enrollment may later capture it (optional toggle).
- **DoD:** migration applies; `CustomerCard` serializers expose `birthday`; no
  other `core/` schema change.

---

## ⬜ Phase 1.6 — Dashboard Completeness

**Goal:** the read-heavy + edit endpoints the dashboard screens need, so a
merchant can be fully measured and managed. Mostly new views in `dashboard/`
(+ a small `uploads` surface); no new app.

### Endpoints (contract §ref → behavior)
| Method · Path | Behavior |
|---|---|
| `GET /cards/{id}/stats` | `CardStats`: holders, stamps_issued, rewards_redeemed, completion_rate, apple_count, google_count — aggregate over `StampLedger`/`Redemption`/`WalletRegistration`. |
| `GET /cards/{id}/qr` | `{join_url, qr_svg, poster_pdf_url}` — `join_url` from the card's `EnrollmentToken` (reuse `enrollment.tokens.issue_enrollment_token`); `qr_svg` server-rendered; `poster_pdf_url` optional/deferred. |
| `POST /uploads` (multipart) | Store logo/image → `{url}`; size/type validated (413/422). Local `MEDIA`/object storage. |
| `GET /customers/{id}` | `CustomerCard` detail (incl. `birthday`). Tenant-scoped 404. |
| `DELETE /customers/{id}` | PDPL delete: cascade the customer's rows; `{ok}`. |
| `GET /customers/{id}/timeline` | Events from `StampLedger` (+ redemptions, messages): `{event_type, delta, balance_after, staff_name, location, gps, at}` (`gps` null — not in core). |
| `GET /analytics/timeseries?from&to&metric=joins\|stamps\|redemptions` | `{points:[{date,value}]}` date-bucketed over the ledger. |
| `GET /analytics/retention?from&to` | `{curve:[{day,retained_pct}], at_risk_count}`. |
| `GET /analytics/by_location?from&to` | `{results:[{location_id,name,stamps,redemptions}]}`. |
| `GET /activity?limit` | Recent feed `{results:[{type,actor_name,customer_name,location,at}]}`. |
| `PATCH /locations/{id}` | Update a location. |
| `GET /locations/{id}/stats` | `{stamps, redemptions, customers}` for the branch. |
| `POST /staff/invite` | Create an `accounts.StaffInvite` (email, role, location), gated by `entitlements.enforce(merchant,"max_staff")`; `{ok}` (email send is Phase 1.7/messaging or console). |
| `PATCH /staff/{id}` | Update role/location/active; **block demoting/deactivating the last Owner** → `CONFLICT` (409). |

### Also
- **Extend `GET /customers` filters** — add `segment` (`lapsed`>30d / `reward_ready`),
  `location`, `search` (the current view has `card`/`status`/`phone`).
- **Enrich `Card` list/detail** — add `holders`, `stamps_issued`, `rewards_redeemed`
  aggregates to match the `Card` schema.
- **Export gating** — when a customer CSV export endpoint is added, gate it with
  `entitlements.check(merchant,"export")`.

### Files
`dashboard/views.py`, `dashboard/serializers.py`, `dashboard/urls.py` (new routes);
a small `dashboard/analytics.py` for the aggregation queries; `uploads` view
(+ `MEDIA_*`/storage settings). Tests: `tests/test_dashboard_phase16.py`.

### Tasks
- [ ] Card stats + QR + enrich list/detail aggregates
- [ ] `POST /uploads` + storage config
- [ ] Customer detail / delete (PDPL) / timeline; extend list filters
- [ ] Analytics timeseries / retention / by_location + activity feed
- [ ] Location patch + stats; staff patch (last-Owner guard) + staff invite (gated)
- [ ] Consume the `birthday` core PR in customer serializers

**Gating:** `max_staff` on invite; `export` on any export; RBAC Admin+ (Owner for staff mutations).
**Migration note:** `dashboard/` only (none expected — reads + the `accounts.StaffInvite` already exists).
**DoD:** every §6 dashboard path returns its contract shape; aggregations correct;
last-Owner protection enforced; lint/type/tests/spectacular clean.

---

## ⬜ Phase 1.7 — Billing & Messaging  *(payments + WhatsApp — external integrations behind faked adapters; real creds on staging)*

**Goal:** real subscriptions (trial→paid→cancel via gateway webhooks), WhatsApp
sending + metering, and the Engage surface (campaigns / segments / automations).

### New models
- `billing.Invoice` — `merchant`, `amount_egp`, `status(paid|pending|failed)`,
  `issued_at`, `pdf_url`, gateway ref. *(migration in `billing/`)*
- `messaging.*` (new app, queue `messaging` already configured):
  - `Campaign` — channel, audience, message, status, schedule_at, sent_at, stats.
  - `Automation` — key (`reward_ready|expiry|birthday|winback|welcome`), enabled,
    channel, timing, template.
  - `WhatsAppUsage` — per-merchant per-month counter (drives `usage.whatsapp_used`).

### Endpoints
| Method · Path | Behavior |
|---|---|
| `GET /billing` | `BillingState`: plan, trial_ends_at, price_egp, usage, next_renewal, payment_method (from `Subscription` + `entitlements.usage`). |
| `POST /billing/subscribe {plan}` | Call a `PaymentGateway` adapter (Paymob/Fawry) → `{checkout_url}`. Adapter faked in tests. |
| `GET /billing/invoices` | Paginated `Invoice`. |
| `POST /billing/cancel {reason}` | `billing.services.lock(merchant)` → `{ok}`. |
| `POST /billing/webhook/paymob` | `security:[]` + HMAC-verify → parse event → `services.activate_plan(...)` / `services.lock(...)`. |
| `POST /billing/webhook/fawry` | Same, Fawry signature scheme. |
| `POST /customers/{id}/message {channel,text}` | One-off PUSH/WHATSAPP; gate WhatsApp via `entitlements.check`/quota (402); enqueue `messaging.tasks.send_whatsapp`. |
| `GET /campaigns` · `POST /campaigns` | List / create+send-or-schedule; WhatsApp gated + metered. |
| `GET /segments` | Computed audiences (`lapsed`, `reward_ready`, by card/location) with counts. |
| `GET /automations` · `PATCH /automations/{key}` | List / toggle+configure; enabled-count gated by `features.automations`. |

### Integrations (faked now, real on staging)
- `billing/gateways/` — `PaymentGateway` interface + `PaymobGateway`/`FawryGateway`
  (httpx); checkout creation + webhook signature verify. Env:
  `PAYMOB_API_KEY`, `FAWRY_MERCHANT_CODE`, `FAWRY_SECURITY_KEY`.
- `messaging/whatsapp.py` — `WhatsAppClient` over the WhatsApp Business API
  (`WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID`); `messaging.tasks.send_whatsapp`.
- **Metering** — increment `WhatsAppUsage` on send; surface in `entitlements.usage`
  (`whatsapp_used`/`whatsapp_quota`); block when quota exhausted (PLAN_LIMIT/402).
- **Automation triggers** — fire `send_whatsapp` on reward-ready / expiry / birthday
  / winback / welcome (hook into ledger events + a daily beat scan).

### Files
`billing/views.py`, `billing/urls.py` (uncomment the include in `config/urls.py`),
`billing/gateways/`, `billing/migrations/` (Invoice); new `messaging/` app
(`models.py`, `tasks.py`, `whatsapp.py`, `views.py`, `urls.py`, migrations).
Tests: `tests/test_billing_http.py`, `tests/test_messaging.py`.

### Tasks
- [ ] Billing HTTP: GET /billing, subscribe (checkout), invoices, cancel
- [ ] Paymob + Fawry webhook handlers (HMAC-verified) → activate_plan/lock
- [ ] `Invoice` model + listing
- [ ] `messaging/` app: WhatsApp client + `send_whatsapp` + `WhatsAppUsage` metering
- [ ] `POST /customers/{id}/message` (gated)
- [ ] Engage: campaigns (CRUD + send/schedule), segments, automations (+triggers)

**Gating:** `whatsapp` capability + monthly quota; `automations` count.
**Migration note:** `billing/` + `messaging/` only.
**DoD:** trial→paid→cancel round-trips via faked gateway payloads; WhatsApp send
enqueued + metered (quota→402); campaigns/automations CRUD; lint/type/tests clean.
**Staging-only:** real Paymob/Fawry checkout + webhook round-trip; real WhatsApp delivery.

---

## ⬜ Phase 1.8 — Hardening, Observability & Scale  *(cross-cutting infra)*

- [x] **Sentry** — errors + Celery + log forwarding, release-tagged. *(done, live)*
- [ ] **Structured logging** — JSON logs, request IDs.
- [ ] **Backups** — nightly off-box `pg_dump` (cron + offsite store) + verified restore.
- [ ] **Secret rotation** — wallet/gateway/WhatsApp keys; document the runbook.
- [ ] **Edge rate-limits** — per-IP / per-token throttling (DRF throttles + Caddy).
- [ ] **DB indexing review** + Celery worker scaling under load.
- [ ] **Frontend Sentry** (when dashboard ships) — browser SDK in `frontend/dashboard`,
      tied to the FE-Dash deploy.

---

## Integration checklist (staging — can't run locally)
- [ ] Stamp → **live pass update on a real iPhone** (Apple register→APNs→pull) + Google.
- [ ] Card edit → Google `LoyaltyClass` re-provisions (`sync_google_class`).
- [ ] Trial→paid→cancel through a **real gateway webhook**.
- [ ] WhatsApp message actually sends + meters.
- [ ] Dashboard (app.stampn.net) talks to the API — confirm prod `.env`
      `CORS_ALLOWED_ORIGINS` includes `https://app.stampn.net`.

---

## Notes
- Per-plan numbers in `billing/plans.py` (limits, `automations`, `analytics`,
  WhatsApp quota) are billing-owned config — confirm with product before launch.
- Contract `plan`/`status` are lowercase + include `trial`; serializers map via
  `billing/wire.py` (no frozen-core change).
- Deploy flow: work on `dev` → promote `prod` (`git checkout prod &&
  git merge --ff-only dev && git push origin prod`) builds + ships the backend image.
