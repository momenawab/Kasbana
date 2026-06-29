# Stampn Backend — Work Brief: **You (Momen)**

**Track:** Platform · Wallets · Billing · Infrastructure
**Your phases:** `1.0` Foundation & Contract (you build it) · `1.1` Enrollment + Wallets · `1.4` Billing + Messaging · plus all infrastructure
**Partner:** Joe owns `1.2` Loyalty engine + `1.3` Dashboard API — see his brief.

> **Read this with the shared *Backend Plan & Variable Contract*.** That document is the single source of truth for every model, enum, field, endpoint, function signature, env var, and error code. This brief tells you *which parts you own and build*; it does not redefine names. **You author the contract in Phase 1.0, then it freezes.** After freeze, any change to a shared name is a joint PR.

---

## 0. How your half works

- **You build the foundation first.** Phase 1.0 produces `core/` + `common/` + the frozen `openapi.yaml`. Nothing else (yours or Joe's) starts until you tag `core-v1`. This is the one hard serial dependency in the whole backend.
- **You own the infra-coupled work.** Wallets, billing, and messaging all need secrets, webhooks, Celery, and the public HTTPS host — which is why they're yours.
- **You implement the seams Joe calls.** Joe's code calls `core.ledger.*` (you implement in 1.0) and `wallets.service.push_update` (you implement in 1.1). Define them as working stubs early so Joe is never blocked.
- **No-conflict rules:** edit only your modules; change shared areas (`core/`, `common/`, `contracts/`) by reviewed PR; keep migrations inside their app; small PRs, green CI, rebase before merge; integrate at each phase end.

## Modules you own

```
config/        settings · urls · celery app          [1.0]
core/          models · enums · constants · auth · ledger · tenancy   [1.0 · shared, FREEZE]
common/        base serializers · pagination · errors · permissions  [1.0 · shared]
enrollment/    join flow · enrollment tokens · consent     [1.1]
wallets/       interfaces · google/ · apple/ · webservice/ · apns · tasks   [1.1]
billing/       paymob · fawry · webhooks · entitlements engine     [1.4]
messaging/     whatsapp · celery senders                   [1.4]
infra/         hetzner · coolify/compose · caddy · ci · backups   [cross-cutting]
```

---

## Contract you rely on (frozen — full definitions in the shared contract)

### You implement these interfaces

```python
# core/ledger.py — THE only way to mutate a balance. You build the bodies in 1.0.
def record_enrollment(customer_card) -> StampLedger: ...
def add_stamp(customer_card, *, staff=None, location=None, delta=1, note="") -> StampLedger: ...
def redeem_reward(customer_card, reward, *, staff=None, location=None) -> Redemption: ...
def current_balance(customer_card) -> int: ...
def is_reward_ready(customer_card) -> bool: ...

# wallets/service.py — the façade Joe calls. You implement Apple + Google behind it.
def provision(customer_card) -> ProvisionResult: ...      # .apple_pass_url, .google_save_url
def push_update(customer_card) -> None: ...               # enqueues push_pass_update

# billing/entitlements.py — Joe's dashboard calls this; you build it in 1.4.
def check(merchant, capability: str) -> bool: ...
def enforce(merchant, capability: str) -> None: ...       # raises PlanLimit -> PLAN_LIMIT
```

### Endpoints you own (exact JSON keys per the contract)

```
POST /api/v1/auth/token            {email, password} -> {access, refresh}
POST /api/v1/auth/refresh          {refresh} -> {access}

GET  /api/v1/enroll/{token}        -> {merchant_name, card_name, reward_title,
                                       stamps_required, color_bg, color_fg, logo_url}
POST /api/v1/enroll/{token}        {customer_phone, customer_name, consent}
                                   -> {customer_card_id, stamp_count, stamps_required,
                                       apple_pass_url, google_save_url}

# Apple Wallet web service (Apple's external spec — camelCase, on the HTTPS host)
POST   /api/v1/wallet/apple/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial}
GET    /api/v1/wallet/apple/v1/devices/{device_library_id}/registrations/{pass_type_id}?passesUpdatedSince=
GET    /api/v1/wallet/apple/v1/passes/{pass_type_id}/{serial}
DELETE /api/v1/wallet/apple/v1/devices/{device_library_id}/registrations/{pass_type_id}/{serial}
POST   /api/v1/wallet/apple/v1/log

# Billing webhooks (you define the bodies to match Paymob/Fawry)
POST /api/v1/billing/webhook/paymob
POST /api/v1/billing/webhook/fawry
```

### Celery tasks you own

```
wallets.tasks.provision_pass(customer_card_id)      # queue: wallet
wallets.tasks.push_pass_update(customer_card_id)    # queue: wallet
wallets.tasks.sync_google_class(card_id)            # queue: wallet
messaging.tasks.send_whatsapp(customer_card_id, template, context)  # queue: messaging
core.tasks.recompute_balance(customer_card_id)      # queue: default
```

### Env vars you need

`SECRET_KEY` · `DATABASE_URL` · `REDIS_URL` · `BASE_URL` · `APPLE_TEAM_ID` · `APPLE_PASS_TYPE_ID` · `APPLE_PASS_CERT_PATH` · `APPLE_PASS_CERT_PASSWORD` · `APPLE_WWDR_CERT_PATH` · `APNS_USE_SANDBOX` · `GOOGLE_WALLET_ISSUER_ID` · `GOOGLE_SA_KEY_PATH` · `WALLET_AUTH_TOKEN_SECRET` · `PASS_BARCODE_SECRET` · `WHATSAPP_API_TOKEN` · `WHATSAPP_PHONE_ID` · `PAYMOB_API_KEY` · `FAWRY_MERCHANT_CODE` · `FAWRY_SECURITY_KEY`

---

## Your phases

### Phase 1.0 — Foundation & Contract  *(shared · build first · FREEZE)*

**Objective:** produce the stable core every other stream depends on, exactly as the shared contract specifies.

**Tasks**
- Project scaffold, split settings, Postgres + Redis + Celery + beat.
- Implement **all** models, `core/enums.py`, `core/constants.py`, the initial `core` migration — per the contract, field-for-field.
- JWT auth, RBAC (`common/permissions.py`), tenant-scoping manager/mixin.
- **Implement `core/ledger.py`** (the shared mutation API) + its custom exceptions (`CooldownActive`, `RateLimited`, `RewardNotReady`).
- `wallets/interfaces.py` + `wallets/service.py` **stubs** (signatures only); `billing/entitlements.py` **stub**.
- `common/` base serializer, cursor pagination, error envelope + `ErrorCode`.
- drf-spectacular wired → **generate and freeze `contracts/openapi.yaml` v1**.
- Set up the mock server from the contract so the frontend + Joe can build against it.

**Exit criteria:** migrations apply; in a shell you can create Merchant→Card→CustomerCard and call `ledger.add_stamp`/`redeem_reward` with correct balances + tenant isolation; OpenAPI committed; **tag `core-v1`**. After this, `core/` schema changes need a joint PR.

**Migration note:** this is the only time `core/` migrations are authored freely.

### Phase 1.1 — Enrollment + Wallets

**Objective:** a customer can enroll and land a live-updating card in Apple + Google Wallet.

**Tasks**
- `EnrollmentToken` issuance + the `GET/POST /enroll/{token}` endpoints; PDPL consent → `CustomerCard.consent_at`. Enrollment calls `core.ledger.record_enrollment` + `wallets.service.provision`.
- **Google:** `LoyaltyClass` per Card, `LoyaltyObject` per CustomerCard, RS256 save URL; `provision_pass`, `sync_google_class`; PATCH on update (auto-push).
- **Apple:** `.pkpass` build + PKCS#7 signing; the 5 web-service endpoints; APNs empty-payload push (`push_pass_update`); `WalletRegistration` + push-token lifecycle.
- Implement `wallets.service.provision/push_update` + `WalletProvisioner`/`WalletUpdater` for both platforms.

**Exit criteria:** enroll via token → working `apple_pass_url` + `google_save_url`; a stamp recorded via the ledger triggers a live pass update on **both** platforms (test the Apple register→APNs→pull loop on a real iPhone first).

**Migration note:** migrations only in `enrollment/`, `wallets/`.

### Phase 1.4 — Billing + Messaging

**Objective:** the 14-day trial, the three paid plans, and the entitlements engine that limits features per plan; WhatsApp sending.

**Tasks**
- Paymob + Fawry subscriptions; the billing webhook endpoints that flip `Merchant.plan` on subscribe / upgrade / downgrade / cancel.
- **14-day trial:** `trial_ends_at` logic; full Growth-level access during trial; lock (data retained) on expiry without conversion.
- **Entitlements engine** (`billing/entitlements.py`): the `plan → {limits + features}` map + `check()` / `enforce()`. This is what Joe's dashboard endpoints (and yours) call to gate actions. Capabilities: `max_cards`, `max_locations`, `max_staff`, `max_customers`, `whatsapp`, `export`, `api`.
- **Messaging:** WhatsApp Business API senders (`send_whatsapp`) for reward-ready / expiry / win-back; metered against the plan's WhatsApp allowance.

**Exit criteria:** trial→paid→cancel all work via webhook; `enforce()` rejects over-limit actions with `PLAN_LIMIT`; WhatsApp notifications fire and are metered.

**Migration note:** migrations only in `billing/`, `messaging/`.

### Cross-cutting — Infrastructure  *(yours throughout)*

Hetzner host + Coolify (or docker-compose + Caddy) · Postgres + Redis · HTTPS (required by the Apple web service) · CI with auto-deploy to staging · secrets in the host vault · nightly off-box `pg_dump` backups · host hardening. The Apple web service and HTTPS must exist from **staging** onward — they can't be tested purely locally.

---

## The integration seam (your handoff to Joe)

Joe builds on two things you provide:
1. **`core.ledger.*`** — frozen in 1.0. His stamp/redeem endpoints write through these, never touching models directly.
2. **`wallets.service.push_update`** — he calls it after every stamp/redeem. It's a working stub from 1.0; your 1.1 makes it real. **Joe's code doesn't change when you fill it in** — that's the point of the stub.
3. **`billing.entitlements.check/enforce`** — his dashboard (1.3) calls this to gate card/location/staff creation. It's a stub until your 1.4; he codes against the interface.

At each phase end: merge both tracks to `main`, deploy to staging, run the phase exit-criteria smoke together.

## Your Definition of Done

Per task: tests pass in CI · matches `openapi.yaml` · ruff+black+mypy clean · any shared-interface change documented · deployed to staging & smoke-tested.
Per phase: exit criteria pass on staging.
