# Stampn — What's Missing / Remaining

> Snapshot **2026-07-01**. Everything in the product roadmap (Phases 1–3) is
> shipped to prod **except tiered cards** (deferred). This doc is the honest list
> of what's *not* done: verification gaps, hardening, and deferred features.
> Ordered by priority.

---

## 🔴 Priority 1 — Verify what's live (biggest gap)

A large amount shipped fast with unit tests but **no real-device / real-service
confirmation**. Tests prove wiring + payloads, not that Apple/Google/the phone
actually behave. Before onboarding a real merchant, walk these live:

- [ ] **Scan → stamp → Google Wallet updates** on a real phone (end to end).
- [ ] **Points card**: scan → add N points → wallet shows "Points" + new balance.
- [ ] **Single-use card**: redeem → pass expires (Google EXPIRED / Apple voided).
- [ ] **Free wallet message / campaign** actually lands as a notification.
- [ ] **Referral**: friend joins via `?ref=` link → both get the bonus stamp.
- [ ] **Branded enrollment**: Growth merchant's custom copy shows, "Powered by" hidden.
- [ ] **New roles**: log in as Marketing / Designer → see only their area.
- [ ] **Scheduled campaign** fires at its `schedule_at` (needs celery beat running).
- [ ] **Billing**: trial → paid → cancel through a **real Paymob** webhook.

---

## 🍏 Priority 2 — Apple Wallet not live

The Apple code path is complete and tested, but **Apple passes are effectively
off in prod**: the enroll page only shows the "Add to Google Wallet" button
(`apple_pass_url` is null), pending a real Apple Developer account + Pass Type ID
cert. iPhone users currently add the *Google* pass.

- [ ] Provision the Apple Pass Type ID cert (`pass.p12` + WWDR) into
      `/opt/stampn/secrets`, set `APPLE_PASS_CERT_*`, verify signing.
- [ ] Enroll page: show the Apple "Add to Wallet" button on iOS once live.
- [ ] Real-iPhone smoke test: register → APNs push → pass pull → stamp update.

---

## 🟡 Priority 3 — Phase 1.8 hardening (partly done)

Done: Sentry (backend), rate-limiting, off-box backups + verified restore.

- [ ] **Structured logging** — JSON logs + request IDs (nothing configured yet).
- [ ] **Frontend Sentry** — browser SDK in `frontend/dashboard` (not installed).
- [ ] **Secret-rotation runbook** — document rotating wallet / gateway keys.
- [ ] **DB indexing review** + Celery worker scaling under load.
- [ ] **Confirm backup cron is installed** on the box (S3 upload works; verify the
      nightly `backup.sh` + weekly `verify_backup.sh` crontab lines are live).

---

## 🟢 Priority 4 — Deferred features

- [ ] **Tiered cards** (silver/gold) — a different model from stamp/points:
      lifetime accrual → membership tiers with per-tier perks. Own future phase;
      touches the core card model + both wallet builders + redemption logic.
- [ ] **Poster PDF (server-side)** — the current poster prints via the browser
      ("Save as PDF"); a true server-rendered PDF is a nice-to-have only.
- [ ] **Apple hero/banner image** — Google has `hero_image_url`; Apple's strip/
      background image isn't wired.

---

## 📋 Housekeeping / debt

- [ ] **Contract drift** — several additive changes aren't in the frozen
      `contracts/openapi.yaml` yet: `/loyalty/scan`, `Card.single_use`,
      `Card.referral_enabled`, `card_type` on CardState, the `specialized_roles`
      / `custom_branding` entitlements, branded-enroll fields. Fold in on the next
      contract bump (drf-spectacular already serves them at `/api/schema`).
- [ ] **WhatsApp** — code kept but dormant (disabled on every plan, Fawry-style).
      Decide if it ever comes back or gets removed.
- [ ] **Fawry** — same: adapter + webhook kept but disabled (Paymob only).
- [ ] **Stale checkboxes** in `Backend-Remaining-Tasks.md` Phase 1.6 — that code
      shipped; the boxes were never ticked.

---

## ✅ For reference — what IS done & live

Core loyalty (enroll, stamp, redeem, wallets), cashier Scan/Till, dashboard
(cards, customers, analytics, campaigns, automations, locations, team, billing,
settings), 5-role RBAC, Paymob billing + webhooks (idempotent), free wallet
messaging, scheduled campaigns, advanced segments, printable poster, single-use
cards, branded enrollment, referrals, points cards, rate-limiting, off-box
backups. **208 backend tests green.** Backend + dashboard deploy in lockstep from
`prod`; Google Wallet live, Sentry live.
