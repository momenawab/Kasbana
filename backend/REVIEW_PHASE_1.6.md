# Code Review — Phase 1.6 (Dashboard Completeness)

**Reviewer:** Momen · **Date:** 2026-06-29 · **Branch:** `dev` (uncommitted working tree)
**Scope:** Phase 1.6 endpoints + the `CustomerCard.birthday` joint-PR.

## Verdict: **Approve with changes**

Strong, plan-aligned work that ships green (full suite + 23 new tests pass; ruff +
black clean). Two correctness bugs should be fixed before merge — one of them
(retention) returns silently-wrong data that the tests don't catch. Everything
else is minor / follow-up.

---

## What was built

New app code in `dashboard/` (+ a `dashboard/analytics.py` module) and one frozen-core
migration. Endpoints, all tenant-scoped and matching the contract shapes:

| Area | Endpoints |
|---|---|
| Cards | `GET /cards/{id}/stats`, `GET /cards/{id}/qr`; `Card` list/detail enriched with `holders/stamps_issued/rewards_redeemed` |
| Uploads | `POST /uploads` (multipart → `{url}`, 413/422) |
| Customers | `GET/DELETE /customers/{id}` (PDPL delete), `GET /customers/{id}/timeline`; list filters extended with `segment` (lapsed / reward_ready), `location`, `search` |
| Analytics | `GET /analytics/{timeseries,retention,by_location}`, `GET /activity` |
| Locations | `PATCH /locations/{id}`, `GET /locations/{id}/stats` |
| Team | `POST /staff/invite` (Owner + `max_staff` gated), `PATCH /staff/{id}` (last-Owner protection) |
| Core | `CustomerCard.birthday` (`DateField(null,blank)`) + migration `0002` |

**Stats:** `dashboard/views.py` +462 · `dashboard/serializers.py` +192 ·
`dashboard/analytics.py` (237) · `tests/test_dashboard_phase16.py` (343, 23 tests).

---

## What's good

- **Tenant scoping is consistent** — `get_scoped` / `for_merchant` on every new view;
  cross-tenant IDs 404. No leaks spotted.
- **Contract alignment** — `Card`/`CustomerCard`/`Staff` response shapes now match the
  frozen `openapi.yaml` schemas (incl. the `id` and `name`/`location_id` corrections).
- **Last-Owner protection** (`StaffDetailView.perform_update`) correctly blocks demoting
  or deactivating the final Owner with `Conflict` (409). Good edge-case thinking.
- **Entitlement gating** kept on the new create surfaces (`staff/invite` → `max_staff`).
- **`analytics.py` is clean** — pure functions, date-range defaulting, gap-filled
  timeseries (returns a point for every day, not just days with events). Nice UX detail.
- **QR** reuses `enrollment.tokens.issue_enrollment_token` rather than reinventing it.
- The `birthday` migration is minimal and exactly the agreed joint-PR.

---

## Findings

### 🔴 BLOCKER — Retention curve returns wrong data (`dashboard/analytics.py` ~L94–L123)
The `first_events` subquery is defined with `OuterRef("pk")` and reused in **two**
querysets:
- in the `cohort` (CustomerCard) queryset → `OuterRef("pk")` = `CustomerCard.pk` ✅
- in the `events` (**StampLedger**) queryset (L121) → `OuterRef("pk")` = `StampLedger.pk` ❌

In the `events` context the subquery filters `StampLedger` by
`customer_card_id = StampLedger.pk`, which never matches, so `first_event_date` is NULL
for every row → the `day` offsets are all empty → **every `retained_pct` is 0**
regardless of real retention.

It passes CI only because `test_analytics_retention_shape` asserts the **shape**
(`len(curve) == 8`), never the values.

**Fix:** in the `events` queryset use a customer-scoped ref, e.g.
`OuterRef("customer_card_id")` (a separate subquery bound to the StampLedger context),
**and** add a test that seeds a small cohort with events on day 0 and day N and asserts
a non-zero `retained_pct`. Also confirm `F("created_at__date") - F("first_event_date")`
yields a `.days`-bearing value on **both** SQLite (tests) and Postgres (prod).

### 🟠 MAJOR — Timeline double-counts redemptions (`dashboard/views.py` ~L435–L437)
`CustomerTimelineView` comments *"Skip redemptions already represented by a REDEEM
ledger event to avoid dupes"* — but the loop appends every `Redemption` row
unconditionally. A redemption therefore appears **twice** (once from the REDEEM ledger
event, once from the Redemption row). Same duplication risk in `analytics.activity_feed`.

**Fix:** either drop the REDEEM ledger events from the timeline and source redemptions
only from `Redemption`, or skip `Redemption` rows that have a matching REDEEM ledger
event. Add a test asserting one redemption → one timeline entry.

### 🟡 MINOR — Upload endpoint hardening (`dashboard/views.py` UploadView)
- The client-supplied filename is concatenated into the storage path
  (`uploads/{ts}_{file_obj.name}`) without sanitization — path-traversal / odd-name risk.
- `content_type` comes from the client and is trusted for the allow-list check (spoofable);
  consider sniffing or validating the extension too.
- Errors are hand-built (`{"error":{...}}`) instead of raising through `common.errors`
  (the shared envelope/handler). Functionally fine, but inconsistent with the rest of the API.

### 🟡 MINOR — `_card_queryset` multi-aggregate annotation (`dashboard/views.py`)
Three `Count(..., distinct=True)` annotations across different relations in one queryset.
`distinct=True` keeps the values correct but the JOIN fan-out can be slow on big merchants.
`CardStatsView` already computes the same numbers via separate `.count()` queries (correct
+ cheaper). Consider standardizing on the per-query approach, or add DB indexes.

### 🔵 NIT
- Invalid `from`/`to` query dates are silently ignored (treated as no-filter) rather than
  returning 400 — minor, but worth a decision.
- Timeline/feed sort on the ISO `at` **string**; fine while everything is UTC, but a typed
  datetime sort is safer.
- Untracked `.opencode/`, `.kilo/`, `redocly.yaml` are in the tree — don't commit them.

---

## Test coverage
23 new tests, good breadth (birthday, stats, QR, uploads 413/422, filters, PDPL delete,
timeline, analytics shapes, location/staff mutations, last-Owner). **Gaps:** the
retention test checks shape only (hides the blocker); no test asserts timeline
de-duplication; no test asserts analytics **values** across a real date range.

---

## Pre-merge checklist
- [ ] Fix retention `OuterRef` scoping + add a value-asserting test (**blocker**)
- [ ] De-duplicate redemptions in timeline + activity feed (+ test)
- [ ] Sanitize upload filename; validate type beyond client `content_type`; use `common.errors`
- [ ] Confirm `core` migration `0002_customercard_birthday` is coordinated with Joe before commit
- [ ] Remove stray untracked tooling files from the commit
- [ ] `python manage.py spectacular` clean; final ruff + black + mypy + pytest green

**Nice work overall — the structure, scoping discipline, and last-Owner handling are
exactly right. Land the two correctness fixes and this is solid.**
