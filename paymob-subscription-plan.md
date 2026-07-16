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
- **The legacy one-time-checkout gateway path is replaced, not kept.** Custom/
  negotiated (Chain "Let's talk") deals get admin-granted access via the
  existing `comp` / `override_plan` tools, not a real checkout.
- **The 6 Paymob Subscription Plans are created by a management command**,
  not by hand in the dashboard — repeatable, versioned, prints the IDs to
  paste into config.

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
| `PAYMOB_API_KEY` | existing | `api/auth/tokens` — legacy, still used for anything not on Intention API |
| `PAYMOB_HMAC_SECRET` | existing | keys **both** HMAC schemes (transaction + subscription), the concatenation differs, the secret doesn't |
| `PAYMOB_SECRET_KEY` | **new** | Bearer/Token auth for the Intention API (`v1/intention/`) — a different key than `API_KEY` |
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
  | `"resumed"`, `"updated"`, card-change types | log only, no state change needed today |

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
- Exact behavior of `use_transaction_amount` on the plan (whether the first
  transaction's amount silently becomes the recurring amount, vs. always
  using the plan's `amount_cents`) — we want the plan's configured
  `amount_cents` to be authoritative, not whatever a coupon-discounted first
  charge happened to be, so we'll likely leave `use_transaction_amount=false`
  and confirm that a discounted first month doesn't retroactively become the
  renewal price.
