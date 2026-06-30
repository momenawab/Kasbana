# Stampn — Product Roadmap

> Created **2026-06-30**. Living doc — check items off as they ship. Each feature
> ships the same way as everything before it: backend-first with tests, gated to
> the right plan, lint/type/spectacular clean, then frontend, then promote to
> `prod`. One feature at a time.

This roadmap captures the post-launch direction agreed after shipping wallet
push messaging + role splitting: **drop the FREE plan, drop WhatsApp** (wallet
push is the free messaging channel now), and build out the feature set that
differentiates the paid plans.

---

## ✅ Recently shipped (context)

- Cashier **Scan / Till** (QR → stamp/redeem) + beep/vibration.
- **Idempotency** on stamp/redeem + billing webhooks.
- **Paymob only** (Fawry disabled, code kept).
- **Rate limiting** (auth + webhooks), **off-box backups** + verified restore.
- **Free wallet messaging** — Apple `changeMessage` + Google `addMessage`; PUSH
  channel delivers real text at no cost; automations fire on the free channel.
- **Roles** — Owner · Admin · Marketing · Designer · Cashier (capability-gated,
  dashboard split by job).

---

## 🧱 Phase 1 — Plan restructure (foundation, do first)

**Goal:** one clean plan/feature matrix as the single source of truth, with the
FREE plan and WhatsApp removed, and the new capabilities gated.

### Decisions
- **Remove the FREE tier.** Tiers become **Starter · Growth · Chain** (+ 14-day
  trial → converts to a paid plan instead of locking to FREE).
- **Remove WhatsApp** as a channel/feature. Wallet push (free, unlimited) is the
  messaging channel. Drop `whatsapp`, `whatsapp_quota`, and the metering gates.
  Keep the WhatsApp adapter code disabled-but-present (the Fawry pattern).
- **Gate new capabilities** behind Growth+:
  - `specialized_roles` — Marketing/Designer roles (Starter = Owner/Admin/Cashier only).
  - `api` — already exists; keep Growth+.
  - `custom_branding` — remove "Powered by Stampn", custom colors on the join page.

### Proposed matrix *(numbers are placeholders — confirm with product)*
| Capability | Starter | Growth | Chain |
|---|---|---|---|
| Cards | 3 | 10 | ∞ |
| Locations | 2 | 10 | ∞ |
| Staff | 5 | 25 | ∞ |
| Customers | 2,000 | 20,000 | ∞ |
| Wallet messaging | ✅ | ✅ | ✅ |
| Automations | 2 | 5 | ∞ |
| Analytics | basic | full | full |
| Specialized roles (Marketing/Designer) | ❌ | ✅ | ✅ |
| API access | ❌ | ✅ | ✅ |
| Custom branding | ❌ | ✅ | ✅ |
| Price (EGP/mo) | 299 | 799 | custom |

### Work
- [ ] `billing/plans.py`: drop FREE from `PLAN_LIMITS`/`PLAN_PRICES_EGP`; drop
      `whatsapp`/`whatsapp_quota`; add `specialized_roles`, `custom_branding`.
- [ ] `billing/entitlements.py`: update `FEATURE_CAPABILITIES`; gate role
      assignment (staff invite/patch checks `specialized_roles`).
- [ ] Trial: convert to a paid plan on expiry (or stay locked — confirm).
- [ ] Messaging: remove the WhatsApp quota/metering gates (keep adapter, disabled).
- [ ] Dashboard: Billing plan matrix reflects the new tiers; Team role dropdown
      hides Marketing/Designer below Growth.
- [ ] Tests + migration note (PlanTier.FREE stays in the enum for old rows; just
      not offered).

---

## ⚡ Phase 2 — Quick wins (reuse what half-exists)

- [ ] **Scheduled wallet campaigns** — `Campaign.schedule_at` already exists; add
      a beat task that sends due campaigns. (Small.)
- [ ] **Advanced segments** — extend the existing `lapsed`/`reward_ready` segment
      catalogue with more filters (by card, location, stamp count, join date). (Small.)
- [ ] **Poster / QR generator** — the deferred `poster_pdf_url`: a printable
      table-tent PDF with the join QR + branding. (Medium.)

---

## 🏗️ Phase 3 — Bigger features (more design each)

- [ ] **Single-use / expiring cards** — per-card "expire after redeem" toggle;
      on redeem, mark the pass expired (Google `state=EXPIRED`, Apple `voided`).
      *(Paused mid-design — see notes below.)*
- [ ] **Branded enrollment page** — custom colors/copy on the public join page
      (gated by `custom_branding`).
- [ ] **Referral program** — customer refers a friend; both earn a stamp. New
      model + tracking + reward logic. (Large.)
- [ ] **More card types** — points-based + tiered (silver/gold), beyond stamps.
      Touches the core card model + both wallet builders. (Largest — save for last.)

---

## Notes / open questions
- **Single-use cards (paused):** cards are currently *reusable* (redeem subtracts
  the threshold and the card continues). "Expire after redeem" makes them
  single-use — neither Apple nor Google can force-delete a pass, but Google
  `EXPIRED` moves it out of active passes and Apple `voided` greys it out. Decide
  whether this is a per-card toggle (recommended) before building.
- **Trial conversion:** today the trial locks on expiry with no conversion. With
  no FREE fallback, decide: auto-prompt to subscribe, or hard-lock until they pay.
- All per-plan numbers are billing-owned config (no contract PR needed to tune).
