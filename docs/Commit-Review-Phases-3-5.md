# Commit Review — Last 6 Commits vs `Admin-Panel-Plan.md`

> Reviewed **2026-07-02** on branch `dev`. Scope: the six commits spanning
> Phase 3 → Phase 5 of the Admin Panel plan, checked against
> `main/docs/Admin-Panel-Plan.md` — **refunds excluded** per the confirmed
> no-refund scope (no refund-initiation capability exists in this system).
>
> **Verdict: ✅ ALL 6 COMMITS PASS — no edits needed.** Every plan requirement
> in scope is implemented, tested, gated, and audited. All quality gates were
> re-run fresh for this review and are green.

---

## 1. Quality gates (re-run for this review, 2026-07-02)

| Gate | Result |
|---|---|
| `pytest` (backend) | ✅ **285/285 passed** (278 committed + 7 in the not-yet-committed `test_console_merchants.py`) |
| `ruff check .` | ✅ All checks passed |
| `black --check .` | ✅ 156 files unchanged |
| `mypy .` | ✅ No issues in 156 source files |
| `manage.py spectacular` | ✅ 0 errors (26 pre-existing warnings, non-blocking) |
| `frontend/admin` lint | ✅ Clean (`--max-warnings 0`) |
| `frontend/admin` build | ✅ Built in ~1s |

---

## 2. Commit-by-commit assessment

### 2.1 `50ccce6` — feat: Phase 3 — Plan Catalogue Management ✅ MEETS PLAN

| Plan requirement | Verified in code |
|---|---|
| `Plan` model (key/name/price_egp/is_public + full limit/feature set) | `billing/models.py:32` — all fields present incl. `archived`, `as_limits()` |
| Seed migration from `PLAN_LIMITS`/`PLAN_PRICES_EGP` | `billing/migrations/0005_seed_plans.py` |
| Hardcoded map kept as fallback when table empty | `billing/plans.py:161-172` — every accessor falls back to the seed constants |
| `GET/POST /plans`, `GET/PATCH /plans/{key}` | `console/views_plans.py` |
| **Archive, not delete** (historical subscriptions) | `PATCH {"archived": true}`; no delete endpoint exists |
| Mutations gated Super-admin/Finance; reads any admin | `IsFinanceAdmin` (`console/permissions.py`) on mutations only |
| Every change audited with before/after | `audit.record(...)` on create/update/archive |
| Security tests (auth boundary + role gate) | `test_console_plans.py` — unauthenticated rejected, support-admin 403 on create/patch, finance can create, duplicate key rejected |

**Deferred, documented:** "draft vs published" staged edits — explicitly noted
in the plan as unneeded scope. Acceptable: edits applying immediately matches
every other admin mutation in the panel.

### 2.2 `cbb6f78` — fix: route checkout price + messaging quotas through DB catalogue ✅ MEETS PLAN (closes a real Phase 3 gap)

The initial Phase 3 refactor only rerouted `entitlements.check/describe`;
checkout price and messaging quotas still read the hardcoded constants — which
contradicted the Phase 3 goal ("edit … prices without a deploy"). Verified fixed:

- `billing/views.py:28,66,100` — subscribe/state price via `plan_price()` (DB-backed).
- `messaging/metering.py:24` + `messaging/views.py:166` — quota + automation
  gates via `plan_limits_map()`.
- `billing/plans.py:140-158` — single cached `_catalogue()` (60s TTL +
  explicit invalidation on every admin write); **archived plans deliberately
  stay in resolution** (archiving only hides from the listing), so an existing
  subscriber's limits/price never break.
- Tests: `test_editing_plan_price_updates_the_checkout_price`,
  `test_archived_plan_still_resolves_its_own_db_limits` — both present, passing.

### 2.3 `08af5a1` — feat: Phase 4 — Subscription Management ✅ MEETS PLAN

| Plan requirement | Verified in code |
|---|---|
| Admin fields: `comp`, `override_plan`, `override_expires_at`, `notes` | `billing/models.py:110-120` (migration `0006`) |
| `effective_plan()` resolution: override → comp → trial/paid/locked | `billing/models.py:139-158` — override wins even over a lock (emergency unblock); comp bypasses billing status |
| `PATCH /merchants/{id}/subscription` + extend-trial/comp/lock/unlock + audit trail | `console/views_subscription.py` — all six endpoints present |
| Reason required on mutations | Enforced by serializers (`test_patch_requires_reason` passes) |
| **Downgrade guardrail** — can't silently drop a paying merchant below usage | `_downgrade_shortfall()` → `409 PLAN_DOWNGRADE_BLOCKED` with per-capability `{usage, limit}` shortfall, overridable with `force: true` |
| Finance/Super-admin gate; reads open | Per-method `get_permissions()` on PATCH; `IsFinanceAdmin` on all POST actions |
| Every action audited with before/after | `audit.record` in all five mutation views |
| Security tests | Role gate, unauthenticated-rejected, comp-bypasses-lock, override-beats-lock, expired-override-falls-back — all present, passing |

### 2.4 `a19fdef` — fix: don't wipe renewal date on a non-plan edit ✅ CORRECT & NECESSARY

Real bug: the Phase 4 PATCH ran `activate_plan()` whenever a plan value was
*present* (the frontend re-sends the current plan on every save), and
`activate_plan` resets `current_period_end` → a notes-only edit silently wiped
a paying merchant's renewal date. Verified fixed at
`console/views_subscription.py:79` — `plan_changed = "plan" in data and
data["plan"] != sub.plan` guards both `activate_plan` **and** the downgrade
check. Regression test
`test_editing_notes_with_unchanged_plan_preserves_renewal_date` present, passing.

### 2.5 `7e416c2` — feat: Phase 5 — Billing, Invoices & Payments (no-refund) ✅ MEETS PLAN (as amended by 2.6)

| Plan requirement | Verified in code |
|---|---|
| `GET /invoices` cross-tenant (status/merchant/date filters, cursor-paginated) + `GET /invoices/{id}` | `console/views_invoices.py:31-51` |
| `POST /invoices/{id}/retry` — FAILED-only, fresh checkout at **current** DB price | `409 INVOICE_NOT_FAILED` guard; `services.retry_invoice` uses `plan_price()` and **prefers `pending_plan` over `plan`** (`services.py:181`) so a first-subscribe failure while TRIALING doesn't retry at FREE/0 — a real trap caught in review, with test `test_retry_of_a_first_subscribe_failure_uses_pending_plan_not_free` |
| `POST /merchants/{id}/invoices` — manual/mark-paid | Default `status="paid"`; `Invoice.note` added **outside** the frozen contract's Invoice shape (migration `0007`); manual invoices exempt from gateway-ref idempotency (`test_manual_invoices_are_not_deduplicated`) |
| `GET /billing/dunning` + `POST .../dunning/notify` | `console/views_billing.py` — notify emails owner (`fail_silently`), audited |
| `GET /billing/reconciliation` | Stale pending **manual** invoices 7+ days; ACTIVE-via-real-checkout with zero PAID invoices (comp/override correctly excluded via `.exclude(provider="")`) — internal-consistency only, honest about the Paymob-reporting-API limitation |
| **No refund anything** | ✅ Confirmed: no `Refund` model, no refund endpoint, no Paymob refund API call. Only remaining "refund" references are the passive `canceled`-webhook classification (`is_refunded` in `paymob.py`, `REFUNDED` in `fawry.py`) — exactly the Phase 1.4 behavior the scope note describes — plus two comment/enum-label strings |
| Role gates + audit | All mutations Finance/Super-admin + audited; reads open to any admin; boundary tests present |

Frontend: global Billing page (Invoices/Dunning/Reconciliation tabs) +
merchant-scoped Billing tab both present under `frontend/admin/src/features/`.

### 2.6 `0b48cc7` — fix: failed upgrade charge must not revoke access ✅ CORRECT & IMPORTANT

The Phase 5 feature commit had the webhook's `failed` branch flip an ACTIVE
merchant to PAST_DUE. Since this system has **no recurring auto-renewal**
(checkouts are one-time; the only billing beat is `expire_trials`), a failed
charge on an ACTIVE merchant is always a *voluntary* upgrade attempt — and
PAST_DUE resolves as locked, so a paying STARTER merchant with a declined
GROWTH-upgrade card would have been locked out of the plan they already paid
for. Verified fixed at `billing/services.py:240-253`: the failed invoice is
recorded, access untouched, with the design rationale in a comment. PAST_DUE
remains an admin-set state (Phase 4 controls) feeding the dunning queue.
Tests: `test_failed_upgrade_charge_never_revokes_a_paying_merchants_access`,
`test_admin_set_past_due_surfaces_in_dunning`,
`test_trialing_merchant_failed_checkout_does_not_flip_to_past_due` — all
present, passing. Plan doc's Phase 5 section was corrected to describe the
real dunning design. This is a genuinely good catch — the plan's own DoD
("dunning surfaces overdue merchants") is still met via the admin-set path.

---

## 3. Cross-cutting checklist (plan §6) — status for these commits

- [x] Models + migrations (`0004`–`0007` billing), endpoints, `AdminAPIView`
      auth+audit+role on every view
- [x] Auth-boundary + permission tests in every phase's test file
- [x] ruff / black / mypy / spectacular clean (re-verified)
- [x] Frontend wired to `/api/admin/v1`, lint + build clean (re-verified)
- [x] Role gates correct (Finance/Super-admin on money-touching mutations)
- [x] Docs: plan checkboxes + shipped summaries updated per phase
- [ ] Promote `dev → prod` for Phases 3–5 — **not yet done** (Phase 1 is live;
      2–5 are on `dev`). This is the expected next step, not a defect.

---

## 4. Minor observations (nothing requires a commit edit)

1. **Untracked test file** — `backend/tests/test_console_merchants.py`
   (7 passing tests) sits uncommitted in the working tree. It should be
   committed (it looks like Phase 2 test coverage that missed its commit).
2. **Commit messages mention a `docs/Admin-Panel-Plan.md` copy** ("main/docs &
   docs") but only `main/docs/Admin-Panel-Plan.md` is tracked in git; the
   Phase 4 commit body also carries a leftover `# Conflicts:` marker for that
   path. Cosmetic only — the tracked plan doc is correct and up to date.
3. **`extend-trial` reason is optional** while all other mutations require it.
   Deliberate and documented in the view's docstring; the action is still
   fully audited. Fine as-is.
4. **Phase 5 feat + fix pair** — the feature commit shipped a design bug
   (webhook PAST_DUE flip) that its sibling fix commit reverted minutes later
   in the same push. Net state on `dev` is correct; the history is honest
   about the review catch.

---

## 5. Bottom line

**All six commits are awesome — no edits needed.** The three feature commits
(Phases 3, 4, 5) implement everything the plan asks for in the no-refund
scope, and the three fix commits each catch a real, high-impact bug (checkout
price not DB-backed; renewal date wiped on notes edit; paying merchant locked
out by a failed upgrade card) with regression tests that prove the fix. Gates
are green across the board. The only follow-ups are housekeeping: commit the
stray `test_console_merchants.py`, then promote `dev → prod` when ready.
