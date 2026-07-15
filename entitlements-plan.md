# Entitlements — close the gaps & simplify the ladder

> Written 2026-07-15 on `dev`. Companion to `pricing-plan.md`.
> Goal: make every advertised tier difference **actually enforced**, and drop the
> two features we've decided not to sell.

---

## 0. Decisions locked in this pass

- **Remove "White-label / suppress Powered by Stampn" from all plans.** The footer
  stays mandatory everywhere. No code work — the `hide_powered_by` field was already
  removed (`branding/migrations/0002`). This is a pricing-page/marketing edit only.
- **Remove "Read-only API tier."** API is not a self-serve ladder feature. It becomes
  a bespoke Custom-only thing (built as part of an integration engagement), so the
  self-serve tiers advertise **no API** at all.

---

## 1. The real work — enforce the leaky limits

Today these are shown as tier perks but the engine never blocks them, so every plan
gets them free. Each needs a gate.

### 1.1 Customer ceiling (`max_customers`) — 🔴 highest priority
- **Now:** counter exists for display; **zero enforcement**. Enrollment never checks it.
  A Starter merchant can enroll unlimited customers past 2,000.
- **Fix:** add `entitlements.enforce(merchant, "max_customers")` in the enrollment
  create path (`enrollment/views.py`), before `CustomerCard` creation. The usage
  counter already exists — just wire the gate.
- **Edge case (from pricing-plan §5.1):** a *customer* enrolling must not be blocked by
  the *merchant's* lapsed plan in a way that breaks a real person's pass. Enforce the
  ceiling on **new** enrollments only; never retro-break existing cards.

### 1.2 Analytics — basic vs full
- **Now:** no plan gate. Analytics endpoints are gated by staff role only, so a Starter
  merchant sees full analytics.
- **Fix:** add `analytics` as a real gate. Proposed split:
  - **Basic (Starter):** `analytics/summary` only.
  - **Full (Growth+):** `timeseries`, `retention`, `wallet_split`, `by_location`.
  - Add `entitlements.check(merchant, "analytics_full")` on the four "full" views → 402.
- Requires promoting `analytics` from a display-only string to a boolean capability
  `analytics_full` in `FEATURE_CAPABILITIES`.

### 1.3 Automations — Growth+ gate + one new automation. See §2 (decided).

### 1.4 Referral program
- **Now:** `card.referral_enabled` is a per-card bool, default off, no entitlement check.
- **Fix:** gate toggling `referral_enabled` on behind a new `referral` capability
  (Growth+). Existing enrolled referral links keep working; only *enabling* it is gated.

---

## 2. Automations — DECIDED (Growth+ feature)

**Automations become a single Growth+ capability.** One boolean gate, honest, sharp
upgrade reason: "automated messages that bring customers back."

- **`welcome`** stays **free for all plans** — it's transactional onboarding, not an
  engagement lever, and blocking a "thanks for joining" message feels petty.
- **All engagement automations are Growth+:** `reward_ready`, `birthday`, `winback`,
  `expiry`, and the new `almost_there` (§2.1).
- **Gate:** add an `automations` capability to `FEATURE_CAPABILITIES`; check it when a
  merchant *enables* any engagement automation row → 402 for Starter.
- Revisit `expiry` separately — it's currently faked (no real stamp-expiry field) and
  may mislead merchants.

### 2.1 New automation — `almost_there` (build now)

Highest-value automation we don't yet have. "You're 1 stamp away from your reward!"
Fires **inline on stamp** when the card is one stamp below its reward threshold — mirror
the existing `reward_ready` hook in the ledger path, just one threshold earlier. Add
`ALMOST_THERE` to `AutomationKey`, a default template, and the trigger in the stamp view.
Growth+ like the rest.

---

## 3. Also fold in (from pricing-plan.md)

- Update prices to the new ladder: **599 / 999 / 2,499** (from 299 / 799). DB-editable,
  no deploy — but the seed in `plans.py` should match.
- Chain `max_customers`: doc says **100,000**, code says unlimited. Pick one.
- Remove the `api` capability from Growth (currently `True`) once API leaves the ladder.

---

## 4. Order of work

1. ✅ Enforce `max_customers` at enrollment (friendly 402; new joins only).
2. ✅ Gate analytics full vs basic (derived `analytics_full` capability; summary stays basic).
3. ✅ Gate referral (new Growth+ `Plan.referral` flag; migration `0014`; only enabling gated).
4. ✅ Automations → Growth+ (Starter allowance 0, `welcome` exempt; migration `0015`).
5. ✅ New `almost_there` automation (fires one stamp before reward).
6. ✅ Reprice to 599 / 999 / 2,499 and drop `api` from Growth **and** Chain (API is
   now bespoke Custom-only); migration `0016`. ⚠️ Pre-deploy: confirm no existing
   Growth merchant relies on the API, or add a per-merchant grandfather override.

Tests + ruff + black + mypy all green through step 6.
