# Kasbana Backend — Remaining Tasks

> Status as of 2026-06-29 (branch `dev`). The frozen `contracts/openapi.yaml`
> (v1.1.0) defines ~45 endpoints; phases 1.0–1.4 + **1.5** are implemented. The
> remaining work is organized into three contract-anchored phases ending in
> **Billing & Messaging**. Full roadmap: `~/.claude/plans/ok-now-we-need-tender-wreath.md`.

---

## ✅ Done
- **1.0–1.3** — auth token/refresh, enrollment, Apple wallet web service, loyalty
  (stamp/redeem/cards), dashboard (cards/customers/staff/locations/analytics-summary).
- **1.4 (partial)** — entitlements engine + 14-day trial: `billing.Subscription`,
  `PLAN_LIMITS`, `check()/enforce()`, `expire_trials` beat task, dashboard gating.
- **1.5 — Account & Session** *(new `accounts/` app; 16 tests; ruff/black/mypy clean)*
  - `POST /auth/signup` (merchant+owner+trial), `/auth/forgot`, `/auth/reset`,
    `GET/POST /auth/invite/{t}`
  - `GET /me` (merchant + entitlements + role, wire-mapped enums)
  - `GET/PATCH /settings/business`, `GET/PATCH /settings/account`,
    `POST /settings/account/password`
  - Supporting: `MerchantSettings`, `StaffInvite`, `PasswordResetToken` models;
    `billing/wire.py` enum mapping; `entitlements.describe()/usage()`.

---

## ⬜ Phase 1.6 — Dashboard Completeness  *(next)*
- [ ] `GET /cards/{id}/stats`, `GET /cards/{id}/qr`; enrich Card list/detail with
      `holders/stamps_issued/rewards_redeemed`
- [ ] `POST /uploads` (logo/image → URL)
- [ ] `GET /customers/{id}`, `DELETE /customers/{id}` (PDPL), `GET /customers/{id}/timeline`;
      extend list filters (`segment`, `location`, `search`)
- [ ] `GET /analytics/{timeseries,retention,by_location}`, `GET /activity`
- [ ] `PATCH /locations/{id}`, `GET /locations/{id}/stats`
- [ ] `PATCH /staff/{id}` (last-Owner protection → 409), `POST /staff/invite`
      (creates the 1.5 `StaffInvite`, gated by `max_staff`)
- [ ] **Joint PR to core:** add `CustomerCard.birthday` (date, null)

## ⬜ Phase 1.7 — Billing & Messaging  *(last — payments + WhatsApp)*
- [ ] Billing HTTP: `GET /billing`, `POST /billing/subscribe` (checkout URL),
      `GET /billing/invoices`, `POST /billing/cancel`,
      `POST /billing/webhook/{paymob,fawry}`; wire `billing/urls.py` into `config/urls.py`
- [ ] `Invoice` model; Paymob/Fawry gateway adapters (faked in tests, real on staging)
- [ ] `messaging/` app: `send_whatsapp` task + faked `WhatsAppClient`; monthly
      `WhatsAppUsage` metering (populates `Usage.whatsapp_used/quota`)
- [ ] `POST /customers/{id}/message`; Engage: `GET/POST /campaigns`, `GET /segments`,
      `GET /automations`, `PATCH /automations/{key}` (`birthday` uses the core PR)

## ⬜ Integration & Infra (staging / cross-cutting)
- [ ] Live pass updates (Apple/Google), real gateway webhook round-trip, real WhatsApp send
- [ ] Sentry + logs/metrics, off-box `pg_dump` backups, secret rotation, rate-limits, scaling

---

### Notes
- Per-plan numbers in `billing/plans.py` (limits, `automations`, `analytics`,
  whatsapp quota) are billing-owned config — confirm with product before launch.
- Contract `plan`/`status` are lowercase + include `trial`; all serializers map
  via `billing/wire.py` (no frozen-core change).
