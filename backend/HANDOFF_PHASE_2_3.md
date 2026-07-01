# Handoff — Phases 2 & 3 (loyalty + dashboard)

Phases 2 (`loyalty/`) and 3 (`dashboard/`) are implemented, tested, and lint/type
clean (ruff · black · mypy · pytest — 82 tests). Endpoints and JSON shapes follow
the frozen contract (§3.6). No `core/` or `common/` changes; no new migrations.

Momen — a few things to confirm on your side, since they touch the seams you own:

## 1. Two contract details the plan left unspecified (assumed your expectations)
- **`POST /api/v1/staff` body** — `{ "email", "password", "role", "location"? }`.
  The endpoint creates the auth `User` + `StaffUser` together in one transaction.
  Owner-only (creating staff escalates access). If the frontend expects a
  different onboarding shape, it's a small change in `dashboard/serializers.py`.
- **`GET /api/v1/customers` filters** — query params `?card=&status=&phone=`
  (`phone` is a contains-match). If different names are expected, it's a few
  lines in `CustomerListView.get_queryset`.

## 2. Other Phase-3 judgment calls (documented in `dashboard/views.py` docstring)
- RBAC: **Admin+** on all dashboard endpoints, except `POST /staff` = **Owner**.
- Card CRUD adds `GET/PATCH /api/v1/cards/{id}` (the contract's bare "PATCH
  /cards" needs an id to target).
- `analytics/summary.repeat_rate` = share of customers with ≥2 `STAMP` events.
- Card create **and** update enqueue `wallets.tasks.sync_google_class`.

## 3. The async seams are tested as *enqueued*, not *executed* — needs your integration pass
Per the plan's interface-test guidance, the wallet hooks are faked in tests:
- loyalty stamp/redeem assert `wallets.service.push_update(card)` is **called**;
- card create/update assert `wallets.tasks.sync_google_class.delay(card_id)` is **enqueued**.

What's **not** verified here (needs Redis + Celery worker + real Apple/Google
creds): that a stamp visibly updates a live pass, and that editing a Card
actually re-provisions its Google `LoyaltyClass`. That's the Phase 1 ↔ 2/3
integration smoke test on your infra.

**Operational dependency:** the `.delay()` calls are not wrapped in broker-error
handling, so the **write** endpoints (`stamp`, `redeem`, `POST/PATCH cards`)
return **500 if the broker is unreachable**. The `CELERY_BROKER_URL` / Redis
must be up alongside the web process. (Read endpoints have no such dependency.)
If you'd prefer writes to degrade gracefully when the broker is down, wrap the
enqueue — say the word and I'll add it.

— Loyalty/dashboard tracks
