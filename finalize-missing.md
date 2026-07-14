# Stampn / Kasbana — Finalize: Missing Features & Remaining Work

> # ⛔ SUPERSEDED — do not use this file
>
> **Go to [`finalize-plan.md`](./finalize-plan.md).** It is the single source of
> truth for what is left to ship.
>
> This is an audit snapshot from **2026-07-03**. Its headline ask — the
> personalized registration page + customizable QR — **shipped** (branded themes,
> styled QR with logo, server poster PDF), as did everything else it lists.
>
> Kept as a historical snapshot because it is the spec the `backend/branding/*`
> docstrings cite as "Phase 1 · finalize-phases". Retired **2026-07-14** (Phase F).

---

> Audit snapshot **2026-07-03**. Covers both apps — the **Merchant Dashboard**
> (`app.stampn.net`, `frontend/dashboard`) and the **Admin Panel**
> (`admin.stampn.net`, `frontend/admin`, backend `console` app, Phases 1–15 all
> shipped). This is the honest list of what's *not* done yet, ordered by what to
> build next. Filename corrected from the requested `filnalize-missing.md`.

---

## 🎯 Priority feature to build — Personalized Registration Page + Customizable QR

**The one the team explicitly wants next.** Today the customer join page (the
page a customer lands on after scanning a merchant's QR) is only *lightly*
personalized, and the QR itself is a plain black square. We want the **QR
template** and the **registration/join page** to be fully brandable per merchant.

### What exists today (the baseline)
- **Join page** — `frontend/dashboard/src/features/enroll/Enroll.jsx`, public
  route `/enroll/{token}`, backed by `GET/POST /enroll/{token}`
  (`backend/enrollment/`). Personalization is limited to:
  - `enroll_headline` (≤80 chars) + `enroll_tagline` (≤160 chars) — **only** on
    `custom_branding` plans (`accounts.MerchantSettings`).
  - Card/merchant colors (`color_bg`, `color_fg`) + logo, a `WalletPreview`, an
    AR/EN toggle, and a "Powered by Stampn" footer hidden for branded plans.
- **QR** — `GET /cards/{id}/qr` (`dashboard/views.py`) returns a **plain black**
  `qr_svg` (python `qrcode` + `SvgImage`), a `join_url`, and an empty
  `poster_pdf_url`. No logo, no brand color, no frame/template.
- There is **no** template/theme model — just the two text fields above.

### What to build
**1. Customizable QR template**
- Let the merchant pick a QR *style*: brand-color modules, a logo embedded in the
  centre, a rounded/dot module style, and an optional framed template
  ("Scan to join", "Collect stamps", branded border, call-to-action strip).
- Offer a few ready-made **poster/QR templates** (layouts) the merchant chooses
  from, pre-filled with their logo/colors/reward text.
- Server-side render both the standalone QR and the composed poster (the
  `poster_pdf_url` is currently a deferred stub — wire it here).
- **Backend:** the plain `qrcode` lib can't embed a logo/color cleanly — evaluate
  `qrcode` with `StyledPilImage` + module drawers + a centre logo (needs Pillow,
  **not currently installed**), or `segno`. Add the chosen dependency.

**2. Personalized registration page**
- Promote enroll-page branding from "2 text fields" to a real **theme**:
  cover/hero image, background color/image, accent/button color, font choice,
  a longer welcome body, and configurable **which fields** to collect
  (name/email/birthday optional-or-required toggles) + custom consent / T&C /
  privacy links.
- Optional: per-**card** overrides (a merchant with several programs may want a
  different look per card), falling back to the merchant default.
- A **live preview** in the dashboard so the merchant sees the page + QR as they
  edit.

### Suggested implementation shape
- **New model** (own app or `accounts`) — e.g. `EnrollTheme` /
  `RegistrationTemplate`: FK to `Merchant` (and optional `Card`), holding
  `template_key`, `cover_image_url`, `bg_color`, `accent_color`, `font`,
  `welcome_body`, `fields_config` (JSON: which fields, required?), `qr_style`
  (JSON: module style, logo on/off, frame template), `terms_url`, `privacy_url`.
  Keep it **out of frozen `core`** — put it in `accounts`/a new `branding` app,
  mirroring how Phase 13–14 models went in their owning app.
- **Extend** `GET /enroll/{token}` to return the resolved theme; **extend**
  `GET /cards/{id}/qr` to accept/return the chosen `qr_style`; add
  `GET/PATCH /settings/enroll-theme` (or `/cards/{id}/enroll-theme`) for the
  dashboard editor. Gate rich theming behind the `custom_branding` entitlement
  (free plans keep the default look + "Powered by Stampn").
- **Frontend (dashboard):** a "Registration page & QR" settings screen with the
  editor + live preview; **frontend (enroll):** consume the theme in `Enroll.jsx`.
- **Migration:** new app/model only; no `core` change. Add tests for theme
  resolution + entitlement gating + QR rendering.

---

## ⏸️ Known & awaiting external approval (not blockers we can close now)

- **Apple Wallet passes** — code path complete + tested, but **off in prod**:
  the enroll page only shows "Add to Google Wallet" (`apple_pass_url` is null),
  pending a real Apple Developer account + Pass Type ID cert (`pass.p12` + WWDR).
  When approved: provision the cert into secrets, set `APPLE_PASS_CERT_*`, show
  the Apple button on iOS, and run a real-iPhone smoke test (register → APNs push
  → pass pull → stamp update). *(Team-tracked; waiting on approval.)*
- **Payment gateway (Paymob) go-live** — Paymob adapter + idempotent webhooks are
  built and run in stub mode; a real trial→paid→cancel round-trip via a live
  Paymob webhook is still pending merchant-account approval. **Fawry** adapter is
  kept but disabled (Paymob-only). *(Team-tracked; waiting on approval.)*

---

## 🟠 Merchant Dashboard — missing / incomplete

- [ ] **Frontend Sentry** in `frontend/dashboard` — the admin panel got the
      browser SDK in Phase 15; the merchant dashboard still has none.
- [ ] **Server-side poster/QR PDF** — `poster_pdf_url` is an empty stub; the
      poster currently prints via the browser ("Save as PDF"). (Folds into the
      priority feature above.)
- [ ] **Customer CSV export** — endpoint + `entitlements.check(merchant,"export")`
      gating were specced (Backend-Remaining-Tasks §1.6) but confirm it's live and
      wired in the UI.
- [ ] **Tiered cards (silver/gold)** — deferred product feature: lifetime accrual
      → membership tiers with per-tier perks. Touches the core card model + both
      wallet builders + redemption logic. Its own future phase.
- [ ] **Apple hero/banner image** — Google has `hero_image_url`; Apple's
      strip/background image isn't wired (also gated on Apple go-live).
- [ ] **Real-device / real-service verification** — much shipped with unit tests
      but no live confirmation: scan→stamp→Google Wallet on a real phone; points
      card balance; single-use expiry; wallet-message notification; referral
      bonus; branded enroll; scheduled campaign firing (needs Celery beat running).

## 🔵 Admin Panel — missing / incomplete

The 15-phase build is code-complete and deployed. Remaining items:

- [ ] **Phase 15 launch items (owner-assigned, not code)** — see
      `main/docs/Admin-Launch-Checklist.md`: fill + activate the Caddy edge
      IP-allowlist (`infra/caddy/Caddyfile.admin-allowlist.example`), set
      `VITE_SENTRY_DSN` for the admin build, manual pentest pass, `pip-audit` +
      `npm audit`, backup-restore test, analytics load-test, eng-lead sign-off.
- [ ] **Partner / affiliate tracking + payout report** — deferred from Phase 11
      (Coupons/Promotions).
- [ ] **Promotion grouping model** — deferred from Phase 11 (coupons ship
      individually; a grouping/campaign wrapper was postponed).
- [ ] **MFA enforcement rollout** — code enforces forced enrolment for privileged
      roles; confirm every real admin has completed enrolment post-deploy.

---

## 🟡 Cross-cutting / hardening / housekeeping

- [ ] **Structured logging** — JSON logs + request IDs (nothing configured).
- [ ] **Secret-rotation runbook** — document rotating wallet / gateway / JWT keys
      (the admin incident runbook exists; a general secrets runbook does not).
- [ ] **DB indexing review + Celery worker scaling** under load.
- [ ] **Confirm backup cron** is installed on the box (nightly `backup.sh` +
      weekly `verify_backup.sh` crontab lines live).
- [ ] **Contract drift** — fold additive changes into the frozen
      `contracts/openapi.yaml` on the next bump (`/loyalty/scan`,
      `Card.single_use`, `Card.referral_enabled`, `card_type`, the
      `specialized_roles` / `custom_branding` entitlements, branded-enroll fields,
      **all `/api/admin/v1/*` console endpoints from Phases 2–15**). drf-spectacular
      already serves them at `/api/schema`.
- [ ] **WhatsApp** — code kept but dormant (disabled every plan). Decide: revive
      or remove.
- [ ] **Fawry** — adapter + webhook kept but disabled. Decide: revive or remove.

---

## ✅ For reference — what IS done & live

- **Merchant side:** core loyalty (enroll, stamp, redeem, Google Wallet), cashier
  Scan/Till, dashboard (cards, customers, analytics, campaigns, automations,
  locations, team, billing, settings), 5-role RBAC, Paymob billing + idempotent
  webhooks, free wallet messaging, scheduled campaigns, advanced segments,
  printable poster, single-use cards, branded enrollment (basic), referrals,
  points cards, rate-limiting, off-box backups.
- **Admin side (all 15 phases, live in prod):** auth/audit spine, merchant
  directory, DB-backed plan catalogue, subscription management, billing/invoices,
  support tools + impersonation, revenue + platform analytics, lifecycle +
  moderation, communications/announcements, coupons/promotions, admin team +
  RBAC matrix, audit-log viewer + PDPL compliance (export / erase / retention),
  platform ops (health, flags, maintenance, task/webhook/wallet monitors), and
  security hardening (TOTP MFA, sessions + rotation, step-up, lockout, Sentry).
- **458 backend tests green;** backend + both frontends deploy in lockstep from
  `prod`; Google Wallet live; Sentry (backend + admin frontend) live.
</content>
