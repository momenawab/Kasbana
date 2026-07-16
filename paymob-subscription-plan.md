# Paymob recurring subscriptions — integration plan

> Written 2026-07-16 on `claude/current-branch-status-lixe2h`. Companion to
> `pricing-plan.md` and `entitlements-plan.md`.
> Goal: replace the current one-time-checkout billing flow with real
> auto-recurring subscriptions via Paymob's Subscription module, matching the
> monthly/annual 599 / 999 / 2,499 ladder already live on the marketing site.

Source docs (Paymob Developer Portal → left nav):
- `authentication-request-generate-auth-token-1`
- `intention-apis/create-intention`, `intention-apis/update-intention`
- `checkout-experiences/unified-checkout-redirection`, `checkout-experiences/pixel-embedded`
- `pay-with-saved-cards/create-card-token`, `cit`, `mit`
- `subscription/create-subscription-plan`, `create-subscription`, `plan-actions`,
  `subscription-actions`, `hmac-calculation-for-subscription-callback`
- `webhook-callbacks-and-hmac/transaction-callbacks`, `hmac`
- Postman collection: `PaymobAccept/API-Postman-Collections` → *Paymob Subscription Module API*

---

## 0. Decisions locked in this pass

- **Monthly + annual ship together**, not monthly-first. Matches the pricing
  page's toggle and `pricing-plan.md`'s ladder — no mismatch between what's
  advertised and what checkout actually charges.
- **The legacy one-time-checkout gateway path is replaced, not kept.**
- **Every public tier is self-service — Starter, Growth *and* Chain**
  (revised 2026-07-16). Chain is an ordinary plan: it appears on Pricing, checks
  out through Paymob, and auto-renews monthly or annually like the others. It is
  **not** "Let's talk". Negotiated deals are a separate **Enterprise** tier
  (§12), not a mode of Chain.
- **The 6 Paymob Subscription Plans are created by a management command**,
  not by hand in the dashboard — repeatable, versioned, prints the IDs to
  paste into config.
- **Card-upfront trial (added 2026-07-16, see §11).** The trial is no longer
  free/card-free. On signup the merchant sees a dashboard intro, then a plan
  gate; to start the 14-day trial they must add a debit/credit card, verified
  by a **1 EGP** charge. At day 14 Paymob auto-deducts the real plan price.
  Defaults taken (changeable): **keep the 1 EGP** (no refund), and **hard-lock
  the dashboard until a card + plan is set** (no card = no access).

## 1. Why this is a real gap, not a polish pass

`billing/services.py::apply_webhook_event` says it outright today:

> *"This system has no recurring auto-renewal (checkouts are one-time)... PAST_DUE (the dunning signal) is reached by an admin, or by a future real renewal system."*

Today a merchant subscribes once, gets a `current_period_end`, and then has to
come back and manually re-checkout every period — nothing charges them
automatically. `BillingStatus.PAST_DUE` exists in the enum but nothing ever
sets it. This plan is that "future real renewal system."

## 2. How the flow changes

**Today:** `SubscribeView` → `PaymobGateway.create_checkout()` → legacy Accept
API (`api/ecommerce/orders` + `api/acceptance/payment_keys` + iframe URL) →
one-time charge → `apply_webhook_event` activates the plan on the transaction
webhook. No recurrence.

**Target:**
1. Ops creates 6 Paymob **Subscription Plans** once (Starter/Growth/Chain ×
   monthly=30d/annual=360d), via a management command. Each plan carries the
   Moto integration ID and our `webhook_url` for subscription callbacks.
2. `SubscribeView` → Paymob **Intention API** (`POST v1/intention/`) with
   `subscription_plan_id` set to the matching Paymob plan ID, using a
   3DS-capable card integration ID (not Moto) for this one linking transaction.
3. Frontend redirects to Paymob's **Unified Checkout**
   (`GET unifiedcheckout/?publicKey=&clientSecret=`) — or embeds the **Pixel**
   SDK — built from the intention's `client_secret`.
4. Customer completes **one** 3DS auth. Paymob saves the card, links it to a
   new **Subscription** instance under the plan, and returns
   `subscription_data.id`.
5. Every billing cycle, Paymob auto-deducts via the plan's Moto integration
   and POSTs a **subscription callback** to the plan's `webhook_url` — a
   different payload shape and HMAC formula from the existing transaction
   webhook (§5 below). This is what drives ongoing renewals.

## 3. Paymob-side prerequisites (dashboard / one-time setup)

| Credential/ID | New? | Purpose |
|---|---|---|
| `PAYMOB_API_KEY` | existing | `api/auth/tokens` — legacy, still used for anything not on Intention API. **Required by the plan-creation command** (§7): Create Subscription Plan authenticates with this auth token, *not* `SECRET_KEY` |
| `PAYMOB_HMAC_SECRET` | existing | keys **both** HMAC schemes (transaction + subscription), the concatenation differs, the secret doesn't |
| `PAYMOB_SECRET_KEY` | **new** | Bearer/Token auth for the Intention API (`v1/intention/`) — a different key than `API_KEY`. Scoped to one Paymob account: a plan ID from a *different* account fails Create Subscription with `404 {"message": "invalid subscription plan id"}` |
| `PAYMOB_PUBLIC_KEY` | **new** | Unified Checkout / Pixel `publicKey` param |
| `PAYMOB_MOTO_INTEGRATION_ID` | **new** | goes on the Subscription Plan; drives the recurring auto-deductions |
| `PAYMOB_CARD_INTEGRATION_ID` | rename of existing `INTEGRATION_ID` | the one-time 3DS card-linking transaction (`payment_methods` on the intention) |
| 6× Paymob plan IDs | **new** | output of the management command (§7), stored on `billing.models.Plan` |

`PAYMOB_IFRAME_ID` (legacy iframe) is dropped — Unified Checkout/Pixel replace
the iframe entirely.

## 4. Data model changes (`billing/models.py`)

```python
class Subscription(...):
    ...
    # Paymob's recurring-subscription instance ID (distinct from gateway_ref,
    # which stays the *transaction* ref). Needed to call suspend/resume/cancel.
    paymob_subscription_id = models.CharField(max_length=64, blank=True)
    # "monthly" | "annual" — doesn't exist today; PLAN_PRICES_EGP is monthly-only.
    billing_interval = models.CharField(max_length=8, choices=[...], default="monthly")

class Plan(...):
    ...
    price_egp_annual = models.DecimalField(...)
    paymob_plan_id_monthly = models.CharField(max_length=64, blank=True)
    paymob_plan_id_annual = models.CharField(max_length=64, blank=True)
```

Migration seeds `price_egp_annual` from the `pricing-plan.md` ladder (5,990 /
9,990 / 24,990 — i.e. 10 months' worth, matching the "2 months free" framing
already implied by the marketing annual toggle).

## 5. Gateway adapter (`billing/gateways/paymob.py`)

- **Replace** `create_checkout`'s body: Intention creation with
  `subscription_plan_id`, `amount_cents`, `currency`, `payment_methods=[CARD_INTEGRATION_ID]`,
  `billing_data`, `notification_url`, `redirection_url`. Returns the same
  `CheckoutSession(checkout_url, gateway_ref)` shape as today — build
  `checkout_url` from Unified Checkout + the intention's `client_secret` so
  `SubscribeView` and the dashboard need minimal changes.
- **Add** `suspend_subscription(paymob_subscription_id)`,
  `resume_subscription(...)`, `cancel_subscription(...)` — thin wrappers over
  `POST api/acceptance/subscriptions/{id}/{suspend|resume|cancel}`.
- **Add** `create_subscription_plan(...)` used only by the management command.
  Wire details verified against the live docs 2026-07-16 (page updated
  2026-06-28): auth is the **legacy** Bearer token from `api/auth/tokens`
  (1-hour expiry), **not** `SECRET_KEY`. The Moto integration goes in a field
  named **`integration`** (a number) — *not* `integration_id`, as an earlier
  draft of this plan said. `frequency` is a **closed enum** — `7, 15, 30, 60,
  90, 180, 360` — so monthly=30 / annual=360; anything else 400s with
  `{"frequency": ["\"5\" is not a valid choice."]}`. Note annual is **360 days,
  not a calendar year**. Other fields: `name` (required, ≤200 chars),
  `amount_cents`, `webhook_url`, `use_transaction_amount` (default false),
  `is_active` (default true), `plan_type` (`"rent"`, the default),
  `number_of_deductions` (default null), `reminder_days`/`retrial_days`
  (strings). The response `id` is a **number**; we store it as a string.
- **Add a second webhook verifier**, `verify_and_parse_subscription_event`.
  This **cannot** reuse `verify_and_parse` — the subscription callback's shape
  (`{"subscription_data": {...}, "trigger_type": "...", "hmac": "..."}`) and
  HMAC formula (`SHA-512("{trigger_type}for{subscription_data.id}")`, keyed by
  the same `PAYMOB_HMAC_SECRET`) are both different from the 19-field
  transaction-webhook concatenation already coded in `_HMAC_FIELDS`.

## 6. New webhook endpoint + service logic

- New route: `billing/webhook/paymob/subscription` (registered as every
  plan's `webhook_url` at creation time).
- New service function (`billing/services.py`), separate from
  `apply_webhook_event` — that one is shaped for a single one-time charge and
  stays only for record-keeping on the initial linking transaction's
  transaction-webhook (order confirmation), not renewals.

  Reads `trigger_type` from the subscription callback:

  | `trigger_type` | Action |
  |---|---|
  | `"Successful Transaction"` | paid `Invoice` + push `current_period_end` forward by the plan's interval (30/360d), keep `ACTIVE` |
  | `"Failed Transaction"` | failed `Invoice`, status → **`PAST_DUE`** (finally reachable) |
  | `"Failed Overdue Transaction"` | failed `Invoice` after Paymob's own retrial window lapsed → lock (`LOCKED`), matching "data retained, access revoked" |
  | `"suspended"` / `"canceled"` | reconcile local status **only if we didn't initiate it** (e.g. customer's bank blocked the card) — check a "we requested this" flag first to avoid double-processing our own suspend/cancel calls |
  | `"Subscription Created"`, `"resumed"`, `"updated"`, `"register_webhook"`, `"change_primary_card"`, `"add_secondry_card"`, `"delete_card"` | log only, no state change needed today |

  **Verified against the live docs 2026-07-16** (portal page *HMAC calculation
  for subscription callback*, updated 2026-06-01). The catalogue above is the
  complete set — an earlier draft of this plan omitted `"Subscription Created"`,
  `"register_webhook"`, `"change_primary_card"`, `"add_secondry_card"` and
  `"delete_card"`. Note `add_secondry_card` carries Paymob's own misspelling and
  must be matched verbatim. The handler should treat an unknown `trigger_type`
  as log-and-ack, never as an error — the catalogue can grow server-side.

## 7. Cancellation — matches the stated refund/cancellation policy exactly

> *"cancel will cancel next sub but after pay the user's subscription will
> continue until end of [period]"*

`Subscription.effective_plan()` / `cancel_at_period_end` already implement
"keep access until period end" correctly and need **no change**. What's
missing is actually telling Paymob to stop charging:

- `services.schedule_cancel()` gains a call to
  `gateway.suspend_subscription(sub.paymob_subscription_id)` **immediately**
  on cancel request. Suspend (not cancel) stops the *next* auto-deduction
  while leaving the subscription resumable — useful if the merchant changes
  their mind before the period lapses.
- `tasks.expire_scheduled_cancellations` (existing Celery task, already flips
  local status to `CANCELED` at period end) additionally calls
  `gateway.cancel_subscription(...)` at that point to permanently close the
  Paymob-side subscription (cleanup; it was already suspended so this doesn't
  change what the customer is charged).
- Re-subscribing (new plan, or undoing a pending cancel) always creates a
  **fresh** Paymob subscription rather than trying to "resume-with-a-different-plan"
  — simpler and avoids edge cases where the new plan/interval doesn't match
  the suspended one. Any still-active old `paymob_subscription_id` is
  cancelled first to avoid double-billing.

## 8. Frontend / dashboard impact

`SubscribeView`'s contract (`POST /billing/subscribe` → `{checkout_url}`)
**doesn't change shape** — but the dashboard's subscribe page needs to render
Paymob's Unified Checkout (simple redirect, no code change) or, if we want an
embedded experience, add the Pixel SDK (`<script src="...paymob-pixel...">`)
instead of today's iframe `src`. Recommend starting with the redirect (zero
frontend JS changes) and revisiting Pixel later if we want an in-page
checkout.

`GET /billing` (`BillingStateView`) should also start returning
`billing_interval` so the dashboard can show "billed annually" correctly.

## 9. Rollout order (build phases)

1. **Migration + settings** — new `Subscription`/`Plan` fields, new env vars
   in `config/settings/base.py`, `.env.example` (or equivalent) updated.
2. **Management command** (`billing/management/commands/create_paymob_plans.py`)
   — calls `create_subscription_plan` 6× (one per Starter/Growth/Chain ×
   monthly/annual), prints the returned IDs. Ops runs it once against Paymob
   sandbox, then again against live, and the IDs get saved onto the `Plan`
   rows (admin console or a data migration/fixture).
3. **Gateway adapter rewrite** — `create_checkout` → Intention flow;
   `suspend_subscription`/`resume_subscription`/`cancel_subscription`;
   `verify_and_parse_subscription_event`.
4. **New webhook route + service function** (§6), wired into `urls.py`.
5. **`schedule_cancel` + `expire_scheduled_cancellations`** call the new
   suspend/cancel gateway methods (§7).
6. **`SubscribeView`/`BillingStateView`** pick up `billing_interval` end to
   end; dashboard subscribe screen adds the monthly/annual choice and updated
   redirect handling.
7. **Sandbox test pass** using Paymob's Subscription Module Postman
   collection + test cards, before touching live credentials.
8. **Docs/env update** for the ops runbook (Paymob dashboard steps for
   getting each credential in §3).

## 10. Open items to verify empirically in sandbox (not assumable from docs alone)

- Whether the **initial** linking transaction fires the classic transaction
  webhook (`notification_url` on the intention) **in addition to** the
  subscription webhook's lifecycle event, or only one of the two — affects
  whether `apply_webhook_event` is still needed at all for the first charge,
  or whether everything (including subscription creation) comes through the
  new subscription webhook exclusively.
- ~~Exact behavior of `use_transaction_amount`~~ — **partly resolved from the
  docs 2026-07-16.** `use_transaction_amount=true` makes the system "use the
  first transaction amount instead of the specified subscription amount"; the
  default is `false`, which uses the plan's `amount_cents`. Critically, Create
  Subscription's docs state `subscription_start_date` "is effective **if the
  `use_transaction_amount` value is false**" — so the two are coupled by
  design, not merely by our preference: the deferred day-14 first charge
  (§11.1) *requires* `use_transaction_amount=false`. This is now a constraint,
  not a choice. Still worth confirming in sandbox that a coupon-discounted 1 EGP
  linking charge doesn't leak into the renewal price.

---

## 11. Card-upfront trial + signup onboarding (added 2026-07-16)

This section **amends §2 (flow), §4 (model), §6 (webhook logic), and §7
(cancellation)** to make the trial card-mandatory and auto-converting. Where it
conflicts with the earlier sections, this section wins.

### 11.1 The signup → trial → auto-charge journey

1. **Sign up** — account + merchant created. The merchant is **not** trialing
   yet and has **no** dashboard access (see 11.4). New `Subscription` starts in
   a pre-trial state, not `TRIALING`.
2. **Dashboard intro** — a first-run onboarding walkthrough that explains what
   the dashboard does (cards, stamps, customers, analytics), then leads into
   the plan gate. Frontend-only (see 11.5).
3. **Plan gate** — the plans render (Starter / Growth / Chain, monthly/annual
   toggle — same catalogue as the marketing Pricing page). The merchant picks
   one; all three check out normally. Enterprise never appears here — it is
   assigned by an admin after a sales conversation (§12).
4. **Card capture (mandatory)** — to start the trial the merchant must add a
   debit/credit card. We create a Paymob **Intention** using the **3DS card
   integration ID** for a **1 EGP** (`amount_cents = 100`) transaction, render
   Unified Checkout / Pixel, and the customer completes one 3DS auth. This:
   - verifies the card is real and authorised,
   - **tokenises + saves** the card (card token callback), and
   - is the **linking transaction** the Paymob subscription attaches to.
   **Decision (default): keep the 1 EGP** — no refund call. It appears on the
   statement as proof of a valid card. (Alternative: auto-refund after
   tokenisation — one extra API call per signup; not chosen.)
5. **Subscription created** — call Create Subscription against the selected
   plan's Paymob plan ID (matching interval), with
   **`subscription_start_date = signup_date + 14 days`** and
   **`use_transaction_amount = false`** so the first *real* deduction is
   deferred to trial end and is the plan's configured `amount_cents` (not the
   1 EGP). Store `paymob_subscription_id` on our `Subscription`.
6. **Trial (14 days)** — full access **at the plan they picked** (not fixed
   Growth). See 11.3.
7. **Day 14 auto-charge** — Paymob deducts the plan's real price from the saved
   card via the Moto integration and fires the subscription webhook
   (`trigger_type = "Successful Transaction"`); our handler books a paid invoice
   and rolls `current_period_end` forward. Recurring every cycle thereafter
   (30 / 360 days).

### 11.2 What changes vs. today's free trial

Today: a `Subscription` row + `trial_ends_at` are created **free** at first
access; `TRIAL_PLAN = GROWTH` is fixed; no card; `expire_trials` locks the
merchant if they never convert. New model:

- **Trial requires a completed card verification + live Paymob subscription.**
  No card ⇒ not trialing ⇒ no access.
- **Trial plan = the selected plan**, not always Growth.
- **Conversion is automatic** (Paymob charges at day 14), so `expire_trials`
  changes role: it's now the **fallback** for "day-14 charge failed / never
  arrived" → `PAST_DUE`/locked, not the normal path.

### 11.3 Model changes (extends §4)

```python
class Subscription(...):
    ...
    # Pre-trial gate: the trial clock only starts once a card is verified.
    # Until then the merchant is locked out (11.4).
    trial_started_at = models.DateTimeField(null=True, blank=True)
    card_verified   = models.BooleanField(default=False)
    card_token_ref  = models.CharField(max_length=64, blank=True)  # Paymob card token
```

- New `BillingStatus.PENDING_CARD` (or reuse a flag) for the post-signup,
  pre-card state. `effective_plan()` returns `None` (locked) in this state.
- `default_trial_end` / `trial_ends_at` are set **at card-verification time**
  (`trial_started_at + 14d`), not at merchant creation.
- `effective_plan()` while `TRIALING` returns the **selected `plan`** (the tier
  they chose at the gate), not `TRIAL_PLAN`.

### 11.4 Access gate (hard-lock default)

**Decision (default): no card ⇒ no dashboard.** Until `card_verified` and a
plan are set, the only thing the merchant can reach is the onboarding intro +
plan/card gate. Every other dashboard route + API is locked (the entitlements
engine already returns "locked" when `effective_plan()` is `None` — we extend
that to the `PENDING_CARD` state). Alternative (not chosen): a read-only
preview dashboard without a card.

### 11.5 Onboarding intro (frontend/dashboard)

- A first-run flow in `frontend/dashboard`: welcome → short feature intro →
  plan selection → card capture (Unified Checkout redirect or Pixel embed).
- Gates the app: while `GET /billing` reports `PENDING_CARD`, the dashboard
  shell renders the onboarding flow instead of the normal app.
- Once the 1 EGP verification succeeds and the subscription is created, the
  merchant lands in the real dashboard, trialing on their chosen plan, with a
  "trial ends in N days · renews at X EGP on <date>" banner.

### 11.6 Cancellation during the trial (extends §7)

- Cancel **during the trial** ⇒ call Paymob **suspend** on the subscription so
  the **day-14 auto-charge never fires**; access continues until day 14 (trial
  end), then locks — consistent with the "access until period end" policy.
- Cancel **after** conversion ⇒ exactly §7 (suspend now, access to
  `current_period_end`, cancel at period end).

### 11.7 Extra sandbox checks (adds to §10)

- Confirm `subscription_start_date` reliably defers the first deduction to day
  14 while the 1 EGP linking transaction settles immediately.
- Confirm the card token from the 1 EGP transaction is the one the recurring
  deductions use (no second card-entry prompt at day 14).
- Confirm what Paymob does if the **day-14 deduction fails** (retrial_days
  behaviour) so `PENDING_CARD` vs `PAST_DUE` vs `LOCKED` transitions match
  reality.

### 11.8 Build-order additions (extends §9)

- Phase 1 (model): add `trial_started_at`, `card_verified`, `card_token_ref`,
  `PENDING_CARD` state; change trial-start + `effective_plan` semantics.
- Phase 3 (adapter): the 1 EGP verification intention + card-token capture;
  Create Subscription with `subscription_start_date`.
- New phase (frontend): the dashboard onboarding intro + plan/card gate.

---

## 12. Enterprise — negotiated tier (added 2026-07-16)

Supersedes the old "Custom" plan and every remaining reference to Chain as
"Let's talk". **Starter / Growth / Chain are self-service. Enterprise is
contact-sales + admin-assigned, and bills exactly like the rest afterwards.**

### 12.1 Why not just a price field on the merchant

A per-merchant custom price does not scale: every new deal re-enters the same
configuration by hand, and nothing is reusable. Instead an Enterprise plan is a
**`billing.Plan` row like any other**, just with `is_public=False` so it never
appears at self-serve. Ops defines *Enterprise Silver / Gold / Platinum* once
and assigns whichever fits.

This needs almost no new billing machinery, because the catalogue is already
built for it: `Plan.key` is a free string ("so custom/negotiated plans can be
added without a code change"), the entitlements engine already resolves limits
from the DB by key, and admins can already create/edit/archive plans via
`POST /api/admin/v1/plans`.

### 12.2 The one structural change

`Subscription.plan` and the frozen `core.Merchant.plan` are constrained to
`PlanTier`, so they cannot hold `ENT_GOLD`. Two levels, therefore:

- **tier** — `PlanTier.ENTERPRISE`, a new *additive* value on the frozen enum
  (same precedent as `Role` gaining MARKETING/DESIGNER post-1.0; agreed
  2026-07-16). This is what `Merchant.plan` mirrors and what the contract's
  plan wire enum reports as `enterprise`.
- **which one** — `Subscription.enterprise_plan`, an FK to the `Plan` row.
  Carries the name ("Enterprise Gold"), price, interval and limits.

`effective_plan()` resolves to the FK's key when set, so entitlements read the
negotiated limits rather than a hardcoded tier.

### 12.3 Billing is the existing flow, unchanged

Each Enterprise `Plan` gets its own Paymob Subscription Plan, exactly like a
public tier — `create_paymob_plans` simply stops filtering on `is_public`. That
means **no new payment path**: the admin-sent "payment link" is the same
Unified Checkout URL `POST /billing/subscribe` already returns, and once the
first 3DS charge links the card, renewals, invoices, dunning, webhooks, retries
and cancellation all reuse §5–§7 verbatim.

### 12.4 Plan model additions

Configurable per Enterprise plan (and harmless on public tiers):

- `max_campaigns` — campaign limit (no equivalent today).
- `priority_support` — boolean.
- `custom_features` — JSON blob, so a one-off capability never needs a
  migration. Keeps the architecture extensible per the brief.

`api` already exists and is exactly what Enterprise re-enables — it left the
public ladder on 2026-07-15 precisely to become bespoke.

**White-label is deliberately absent.** Decision 2026-07-16: "Powered by
Stampn" is removed from *every* plan, so there is nothing to gate — the flag
would always be true. This reverses the 2026-07-15 "footer is mandatory"
decision.

### 12.5 Merchant-facing (§8 of the brief)

The billing page shows the negotiated plan as a first-class subscription:
Current Plan = *Enterprise*, Plan Name = *Enterprise Gold*, its price, interval,
renewal date and status — plus the enabled limits/features. It never exposes the
pricing editor or the plan configuration; those are admin-only.

### 12.6 Build order

1. Chain self-service everywhere + docs (done).
2. `Plan` gains `max_campaigns` / `priority_support` / `custom_features`.
3. `PlanTier.ENTERPRISE` + `Subscription.enterprise_plan` + assignment +
   `effective_plan` resolution + `create_paymob_plans` covering non-public plans.
4. Admin panel: manage Enterprise plans, assign one, send the payment link.
5. Dashboard billing page: the Enterprise view above.
6. Marketing pricing: Enterprise "Let's Talk" (done — replaced Custom).
