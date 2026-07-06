# Stampn (Kasbana) — Launch Checklist

> What stands between the current build and **starting the business** with real,
> paying merchants. Snapshot **2026-07-06**. The product is technically ~90%
> built (458 backend tests green; both dashboards + admin panel live in prod;
> Google Wallet working). What's left is mostly **not code** — external
> approvals, real-world verification, ops sign-off, and the commercial/legal
> layer. Ordered by the critical path.

**Critical path in one line:** Paymob approved → Apple cert → live verification
on real phones → legal/pricing published → sign one pilot merchant.

---

## 🔴 Hard blockers — cannot take a paying customer without these

- [ ] **Paymob merchant account go-live** — billing runs in *stub mode*. Get a
      real Paymob account approved (needs the legal entity + bank account below),
      then prove one `trial → paid → cancel` round-trip through a **live Paymob
      webhook**. Until this works you literally cannot collect money.
      *(Fawry adapter exists but is disabled — Paymob only.)*
- [x] **Apple Developer account + Pass Type ID cert** — the Apple Wallet code
      path is complete but *off in prod*; iPhone users currently get the Google
      pass. In Egypt a large share of café/salon customers skew iPhone.
  - [x] Provision `pass.p12` + WWDR into `/opt/stampn/secrets`.
  - [x] Set `APPLE_PASS_CERT_*`; verify signing.
  - [x] Enroll page: show the Apple "Add to Wallet" button on iOS once live.
  - [x] Real-iPhone smoke test: register → APNs push → pass pull → stamp update.

---

## 🟠 Real-device / real-service verification — biggest technical risk

Much shipped with unit tests that prove *wiring + payloads*, not that
Apple/Google/the phone actually behave. Walk these **live on a real phone**
before onboarding merchant #1:

- [ ] Scan → stamp → **Google Wallet updates** end-to-end.
- [ ] **Points card**: scan → add N points → wallet shows "Points" + new balance.
- [ ] **Single-use card**: redeem → pass expires (Google EXPIRED / Apple voided).
- [ ] **Free wallet message / campaign** lands as a real notification.
- [ ] **Referral**: friend joins via `?ref=` link → both get the bonus stamp.
- [ ] **Branded enrollment**: Growth merchant's custom copy shows, "Powered by" hidden.
- [ ] **New roles**: log in as Marketing / Designer → see only their area.
- [ ] **Scheduled campaign** fires at its `schedule_at` (needs **Celery beat** running).
- [ ] **Billing**: trial → paid → cancel through a real Paymob webhook (folds into blocker #1).

---

## 🟡 Ops / launch sign-off (non-code, owner-assigned)

- [ ] **Admin edge allowlist** — activate `infra/caddy/Caddyfile.admin-allowlist.example`
      with the team's real static egress IPs; verify from an allowed **and** a
      blocked IP.
- [ ] **Confirm HTTPS** (Let's Encrypt) valid on the admin host.
- [ ] **Set `VITE_SENTRY_DSN`** (+ env/release) for the admin frontend build;
      confirm a test error surfaces in Sentry.
- [ ] **Frontend Sentry for the merchant dashboard** — browser SDK not installed
      yet (admin panel has it; dashboard doesn't).
- [ ] **Manual pentest pass** — cross-tenant leakage, impersonation-abuse, IDOR
      on `/api/admin/v1/*`, token-boundary fuzzing.
- [ ] **`pip-audit`** on the backend image + **`npm audit`** on the frontends.
- [ ] **Backup restore test** — confirm nightly `backup.sh` + weekly
      `verify_backup.sh` crontab lines are actually installed on the box; do one
      real restore.
- [ ] **MFA enrolment** — seed each real team member as an `AdminUser`; confirm
      each completes MFA on first login; decide prod access-token lifetime.
- [ ] **Load-test** the cross-tenant analytics queries at expected merchant
      volume; add DB indexes if any aggregate is slow.
- [ ] **Eng-lead sign-off** — all boxes above checked, launch approved.

---

## ⚪️ The business layer — not tracked anywhere in the repo

The engineering docs are complete; these commercial/legal items are what
actually make it a *business*:

- [ ] **Legal entity + bank account** — required anyway for Paymob KYC.
- [ ] **Pricing finalized & public** — plans exist in code; decide the price
      list and put it on the site.
- [ ] **Terms of Service + Privacy Policy + PDPL consent** — you collect customer
      PII (name/email/birthday). Admin side has PDPL export/erase, but the
      public-facing enroll page needs real legal copy + consent / T&C / privacy
      links.
- [ ] **First merchants / pilot** — 3–5 friendly cafés to run the live
      verification above *and* be your first references.
- [ ] **Support channel** — WhatsApp/email/phone for "my stamp didn't land."
      (WhatsApp integration is coded but dormant — decide: revive or remove.)
- [ ] **Personalized Registration Page + Customizable QR** (team's stated next
      feature) — the QR is currently a plain black square with no logo/branding.
      Not a launch blocker, but it's the polish that makes merchants say yes.
      See `finalize-missing.md` for the build shape.

---

## 🟢 Deferred — explicitly *not* needed to launch

- [ ] **Tiered cards (silver/gold)** — separate product feature, own future phase.
- [ ] **Server-side poster/QR PDF** — poster prints via the browser today; folds
      into the branded-QR feature.
- [ ] **Apple hero/banner image** — Google has `hero_image_url`; Apple's strip/
      background isn't wired (also gated on Apple go-live).
- [ ] **Structured logging** (JSON logs + request IDs), **secret-rotation
      runbook**, **contract drift** fold-in to `contracts/openapi.yaml`.

---

## ✅ For reference — what IS done & live

- **Merchant side:** core loyalty (enroll, stamp, redeem, Google Wallet), cashier
  Scan/Till, dashboard (cards, customers, analytics, campaigns, automations,
  locations, team, billing, settings), 5-role RBAC, Paymob billing + idempotent
  webhooks (stub), free wallet messaging, scheduled campaigns, advanced segments,
  printable poster, single-use cards, branded enrollment (basic), referrals,
  points cards, rate-limiting, off-box backups.
- **Admin side (all 15 phases live):** auth/audit spine, merchant directory, plan
  catalogue, subscriptions, billing/invoices, support + impersonation, revenue +
  platform analytics, lifecycle + moderation, communications, coupons/promotions,
  admin RBAC, audit-log viewer + PDPL compliance, platform ops monitors, security
  hardening (TOTP MFA, sessions + rotation, step-up, lockout, Sentry).
- **458 backend tests green;** backend + both frontends deploy in lockstep from
  `prod`; Google Wallet live; Sentry (backend + admin frontend) live.
