# Stampn Backend — Work Brief: **Joe**

**Track:** Loyalty Engine · Anti-Fraud · Dashboard API
**Your phases:** `1.2` Loyalty engine + anti-fraud · `1.3` Dashboard API
**Partner:** Momen owns `1.0` Foundation, `1.1` Enrollment + Wallets, `1.4` Billing + Messaging, and infra — see his brief.

> **Read this with the shared *Backend Plan & Variable Contract*.** That document is the single source of truth for every model, enum, field, endpoint, and signature. This brief tells you *what you build and which frozen symbols you import*. **You never redefine anything in `core/` — you import it.** v1 is **stamp cards only**: no points math, no tiers.

---

## 0. How your half works

- **You start the moment `core-v1` is tagged.** Momen builds the foundation (`core/`) first and freezes it; from that point you run **fully in parallel** with him.
- **You own product logic, not infrastructure.** You never touch wallets, billing, certs, or the server — you call interfaces Momen exposes.
- **You code against stubs.** `wallets.service.push_update` and `billing.entitlements.*` exist as stubs from 1.0. Build against them now; when Momen's 1.1/1.4 land, your code doesn't change. Use a **fake** `push_update` in your tests.
- **No-conflict rules:** edit only `loyalty/` and `dashboard/`; import from frozen `core/` + `common/` (read-only); never reach into `wallets/` internals — only the façade; keep migrations inside your apps; small PRs, green CI, rebase before merge.

## Modules you own

```
loyalty/     stamp · redeem · anti-fraud surface     [1.2]
dashboard/   analytics · merchant/card/staff/location config api   [1.3]
```

---

## Contract you rely on (frozen — you import, never redefine)

### Functions you call (do not write to models directly)

```python
from core import ledger
ledger.add_stamp(customer_card, *, staff, location, delta=1, note="") -> StampLedger
    # raises CooldownActive / RateLimited  ->  map to COOLDOWN_ACTIVE / RATE_LIMITED
ledger.redeem_reward(customer_card, reward, *, staff, location) -> Redemption
    # raises RewardNotReady  ->  REWARD_NOT_READY
ledger.current_balance(customer_card) -> int
ledger.is_reward_ready(customer_card) -> bool

from wallets import service as wallet     # façade — STUB until Momen's 1.1; fake it in tests
wallet.push_update(customer_card) -> None

from billing import entitlements          # STUB until Momen's 1.4
entitlements.enforce(merchant, "max_cards")     # raises PlanLimit -> PLAN_LIMIT
entitlements.check(merchant, "export") -> bool
```

### Enums you use (`core/enums.py`)

`LedgerEvent{STAMP, REDEEM}` · `CardType{STAMP}` (stamp only in v1) · `CardStatus` · `CustomerCardStatus` · `RedemptionStatus` · `Role{OWNER, ADMIN, SCANNER}`

### Models you read (definitions in the contract — read-only for you)

`Merchant · Location · StaffUser · Card · CustomerCard · StampLedger · Reward · Redemption · WalletRegistration`

### Constants you use (`core/constants.py`)

`STAMP_COOLDOWN_SECONDS` · `MAX_STAMPS_PER_CARD_PER_DAY` · `MAX_STAMPS_PER_STAFF_PER_MIN` · `DEFAULT_PAGE_SIZE`

### Endpoints you own (exact JSON keys per the contract)

```
# Loyalty (Phase 1.2)
POST /api/v1/loyalty/stamp
  {customer_card_id, delta=1} -> {customer_card_id, stamp_count, stamps_required, reward_ready}
POST /api/v1/loyalty/redeem
  {customer_card_id, reward_id} -> {redemption_id, status, stamp_count}
GET  /api/v1/loyalty/cards/{customer_card_id}
  -> {customer_card_id, customer_name, stamp_count, stamps_required, reward_ready, status}

# Dashboard (Phase 1.3)
GET/POST/PATCH /api/v1/cards            # Card CRUD
GET            /api/v1/customers        # CustomerCard list, filterable
GET/POST       /api/v1/staff
GET/POST       /api/v1/locations
GET            /api/v1/analytics/summary
  -> {enrollments, active_cards, redemptions, apple_count, google_count, repeat_rate}
```

### Error codes you raise (`common/errors.py`)

`VALIDATION_ERROR · NOT_FOUND · PERMISSION_DENIED · COOLDOWN_ACTIVE · RATE_LIMITED · REWARD_NOT_READY · PLAN_LIMIT · CONFLICT`

---

## Your phases

### Phase 1.2 — Loyalty Engine + Anti-Fraud

**Objective:** staff can stamp and redeem reliably; balances are correct; fraud is blocked server-side. Stamp-only — no points logic.

**Tasks**
- `POST /loyalty/stamp` — resolve + tenant-scope the `CustomerCard`, call `ledger.add_stamp(...)`, then `wallet.push_update(card)`, return the contract response.
- `POST /loyalty/redeem` — validate reward-ready via `ledger.is_reward_ready`, call `ledger.redeem_reward(...)`, then `wallet.push_update(card)`.
- `GET /loyalty/cards/{id}` — card status for the scanner.
- **Anti-fraud** (enforced server-side, written into `StampLedger`): per-card cooldown (`STAMP_COOLDOWN_SECONDS`), per-card/day and per-staff/min velocity limits, staff + location binding on every event. Map the ledger exceptions to the right error codes.

**Reference example**
```python
def post(self, request):
    card = get_scoped(CustomerCard, request, id=request.data["customer_card_id"])
    ledger.add_stamp(card, staff=request.staff, location=request.staff.location)
    wallet.push_update(card)          # stub now; real after Momen's 1.1 — your code unchanged
    return Response({
        "customer_card_id": str(card.id),
        "stamp_count": card.stamp_count,
        "stamps_required": card.card.stamps_required,
        "reward_ready": ledger.is_reward_ready(card),
    })
```

**Exit criteria:** stamp/redeem update the ledger + cached `stamp_count` correctly; fraud guards reject abuse with the right `ErrorCode`; against a **fake** `push_update` the loop is correct; against the real one (post-integration) the pass updates live.

**Migration note:** `loyalty/` migrations only (e.g. fraud audit indexes). No `core/` edits.

### Phase 1.3 — Dashboard API

**Objective:** the API the client dashboard (Stage 2) consumes — card config, customers, analytics, team.

**Tasks**
- **Card CRUD** (`/cards`) — create/update a stamp-card program; on create or branding change, enqueue `wallets.tasks.sync_google_class(card_id)` so the Google class re-provisions. Gate creation with `entitlements.enforce(merchant, "max_cards")`.
- **Customers** (`/customers`) — list + filter `CustomerCard`; per-customer detail (history from `StampLedger`, redemptions, last visit). Gate export with `entitlements.check(merchant, "export")`.
- **Staff & locations** (`/staff`, `/locations`) — CRUD, gated by `max_staff` / `max_locations`.
- **Analytics** (`/analytics/summary`) — aggregations over `StampLedger`, `Redemption`, and `WalletRegistration` (the Apple-vs-Google split comes from `WalletRegistration.platform`).

**Exit criteria:** a merchant can be fully configured and measured via the API; all create endpoints respect plan limits via the entitlements engine.

**Migration note:** `dashboard/` migrations only. No `core/` edits.

---

## The integration seam (what you depend on from Momen)

| You call | Owner | Status until integrated |
|---|---|---|
| `core.ledger.*` | Momen (1.0) | **Real from day one** — frozen in foundation |
| `wallets.service.push_update` | Momen (1.1) | Stub / your fake — becomes real, no code change |
| `billing.entitlements.check/enforce` | Momen (1.4) | Stub — code against the interface now |
| `wallets.tasks.sync_google_class` | Momen (1.1) | Stub task — real after 1.1 |

At each phase end: merge both tracks to `main`, deploy to staging, run the exit-criteria smoke with Momen.

## Your Definition of Done

Per task: tests pass in CI (incl. a fake `WalletUpdater`) · matches `openapi.yaml` · ruff+black+mypy clean · no `core/` edits without a joint PR · deployed to staging & smoke-tested.
Per phase: exit criteria pass on staging.

> **One rule above all:** never write to `StampLedger` or `CustomerCard.stamp_count` directly. Every balance change goes through `core.ledger`. That single discipline is what keeps your half and Momen's half consistent.
