# Plan — Phase E.1: Partner / merchant-referral program (comp-months)

> Decisions captured 2026-07-11 from the owner. This supersedes the loose
> "partner/affiliate + payout report" line in `finalize-plan.md` (Phase E), which
> is now defined concretely below.

## What it is

A **merchant-refers-merchant** program. An existing merchant (the **partner**)
has a referral code/link; when a merchant they referred **first converts to a
paid subscription**, a **one-time** reward fires (if the program is enabled):
**both** the partner and the new merchant receive **free subscription months**
(comp), applied to their own subscriptions. All amounts + the on/off switch are
configured in the admin panel.

### Decisions (owner)

- **Partner = an existing merchant.** The reward is applied as comp months to the
  partner's own subscription (so a partner must be a merchant).
- **Attribution = both:** auto via referral code at merchant signup, **and**
  manual admin assignment/correction.
- **Reward = free months (comp), one-time, not a percentage.** Fires on the
  referred merchant's first paid conversion.
- **Recipients = both** the partner and the new merchant.
- **Config = global default + per-partner override:** `enabled`,
  `partner_free_months`, `merchant_free_months`. Toggleable in admin.

## Data model (new `partners` app — `core` stays frozen)

- **`PartnerProgramConfig`** (singleton global default): `enabled` (bool, default
  False — off until switched on), `partner_free_months` (default 1),
  `merchant_free_months` (default 1). One row, `get_or_create`.
- **`Partner`**: `merchant` (OneToOne → core.Merchant), `code` (unique, indexed),
  `active` (default True), and nullable overrides `enabled_override`,
  `partner_free_months_override`, `merchant_free_months_override` (null = fall
  back to the global default). A `resolved_config` helper merges override→global.
- **`PartnerReferral`**: `partner` (FK), `referred_merchant` (OneToOne → Merchant
  — a merchant is referred by at most one partner), `attributed_via`
  (`signup_code` | `admin`), `converted_at` (nullable), `reward_granted` (bool —
  idempotency guard), `partner_months_granted` / `merchant_months_granted`
  (recorded at grant time).

## Billing integration

- Add **`billing.services.grant_free_months(merchant, months)`** — pushes
  `current_period_end` forward by N months from `max(now, current_period_end)`,
  giving N months of paid access with no charge (best-effort; a no-op for
  `months <= 0`). This is the "free months" primitive the codebase currently
  lacks (only `set_comp(bool)` / `extend_trial(days)` exist).
- Hook the **conversion trigger** into `billing.services.apply_webhook_event`
  (where a sub first becomes paid/active): call
  `partners.services.on_merchant_converted(merchant)`, which — if the program is
  enabled, the merchant has a `PartnerReferral`, and `reward_granted is False` —
  grants both sides their months, stamps `converted_at` + `reward_granted`, and
  records the granted amounts. Wrapped best-effort so a reward failure never
  breaks the payment webhook. Self-referral (partner == referred) is impossible
  by construction (a merchant can't be its own referrer).

## Attribution capture

- **Signup:** thread an optional `referral_code` through the merchant
  registration endpoint; if it resolves to an active partner (and isn't the same
  merchant), create `PartnerReferral(attributed_via="signup_code")`. Unknown /
  blank code = no referral (today's behavior).
- **Admin:** `POST /partners/{id}/referrals {merchant_id}` creates/【re】assigns
  attribution manually (`attributed_via="admin"`).

## Admin API (`console/`, gated `PARTNERS_MANAGE` — Finance/Super-admin)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/partners` | list (cursor-paginated); any admin reads |
| POST | `/partners` | create a partner from an existing merchant + code (Finance+) |
| GET | `/partners/{id}` | detail + referral/reward totals |
| PATCH | `/partners/{id}` | code / active / overrides (Finance+) |
| DELETE | `/partners/{id}` | remove partner (Finance+) |
| GET | `/partners/{id}/referrals` | the reward/payout report rows |
| POST | `/partners/{id}/referrals` | manual attribution (Finance+) |
| GET/PATCH | `/partner-config` | global default (Finance+) |

- New `Permission.PARTNERS_MANAGE = "partners.manage"` in `console/rbac.py`,
  granted to `FINANCE`. Every mutation audited via `console.audit.record`.

## Admin frontend (`frontend/admin/src/features/partners/`)

`PartnersHome.jsx`: global config panel (enabled + default months), partner list
(merchant, code, active, #referrals, #converted), create-partner form, and a
per-partner detail with the referral/reward report (referred merchants,
converted date, months granted to each side).

## Tests (`backend/tests/test_partners.py`)

Partner CRUD + `PARTNERS_MANAGE` gate (Support/Read-only 403); code uniqueness;
signup attribution (valid code → referral, unknown/blank → none); manual
attribution; a merchant referred by at most one partner; **conversion grants both
sides their months exactly once** (idempotent on a second webhook); global vs
per-partner override resolution; `grant_free_months` math; report totals; program
disabled → no grant.

## Definition of done

Full backend gate (ruff/black/mypy/check_openapi/pytest) + admin frontend gate
(eslint/vitest/build) green. A merchant signs up via a partner's code, converts
to paid, and both the partner and the new merchant gain the configured free
months exactly once; admin can toggle the program, set global + per-partner
amounts, assign attribution manually, and read the reward report. Bundle-promote
to prod with E.2 on approval.
