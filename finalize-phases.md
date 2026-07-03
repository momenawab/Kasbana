# Stampn / Kasbana — Finalize: Phased Build Plan

> Turns [`finalize-missing.md`](./finalize-missing.md) into an ordered, buildable
> roadmap. Each **build phase** is self-contained — it lists everything needed to
> do it (backend, frontend, data, tests, definition-of-done) so it can be picked
> up cold. Sequenced by priority: the personalized registration page + QR first
> (Phases 1–2), then dashboard hardening, admin deferrals, and platform
> housekeeping.
>
> Two things are **out of scope for these phases** and tracked separately at the
> bottom: (a) items awaiting external approval (Apple Wallet, Paymob go-live), and
> (b) owner/infra launch tasks (edge allowlist, pentest, sign-off). We can't close
> those from code.
>
> **Ground rules for every phase**
> - Never modify frozen `core` contract models. New models live in their owning
>   app (or a new app), mirroring how Phases 13–15 shipped.
> - Quality gate per backend phase: `ruff` + `black` + `mypy` + `drf-spectacular`
>   + `pytest` all green. Per frontend phase: `eslint --max-warnings 0` +
>   `vite build` + `prettier`.
> - Work on `dev`; promote to `prod` (merge `--no-ff`) only when a phase is green
>   and the user approves.

---

## Phase 1 — Registration Theme & QR: backend foundation 🎯 PRIORITY ✅ DONE

> **Status: shipped on `dev`.** New `branding` app + `RegistrationTheme` model,
> `resolve_theme` gating, styled QR (colored/shaped SVG), extended
> `GET /enroll/{token}` (nested `theme`), styled `GET /cards/{id}/qr`, and the
> editor endpoints `GET/PATCH /settings/enroll-theme` +
> `GET/PATCH/DELETE /cards/{id}/enroll-theme`. 13 new tests; full gate green
> (470 pytest). **Scope calls made during the build:**
> - **No new binary deps.** The QR is a hand-rolled colored/shaped **SVG** from
>   the `qrcode` module matrix — no Pillow. **Logo-in-QR-centre + the server
>   poster PDF moved to Phase 3** (both need Pillow *and* the prod-media-serving
>   fix — media 404s in prod today since `config/urls.py` only serves it under
>   `DEBUG`).
> - **Cover image reuses the existing `/uploads` endpoint** (stored as a URL
>   string like `Card.logo_url`), so no dedicated cover-upload endpoint was added.
> - `hide_powered_by` defaults **True** (branded plans stay white-label by
>   default, preserving prior behaviour); free plans always show the footer.

**Goal.** Give every merchant a real, brandable registration-page theme and a
styled QR, replacing today's two text fields (`enroll_headline`,
`enroll_tagline`) and plain-black QR.

**Why first.** Explicitly the team's next priority; everything in Phase 2 (the
editor UI) and the poster-PDF item in Phase 3 depend on this backend.

### New app & model
- New Django app **`branding`** (keeps it out of frozen `core`; own migrations).
- Model **`RegistrationTheme`**:
  - `merchant` FK (required); `card` FK **nullable** (a null-card row is the
    merchant default; a card-scoped row overrides it for that program).
  - `unique_together = (merchant, card)` so there's one default + one per card.
  - Page theme: `template_key` (choices: `classic|hero|minimal|bold`),
    `cover_image` (ImageField), `bg_color`, `accent_color`, `button_text_color`
    (all hex, validated), `font` (enum of a small safe set), `welcome_body`
    (Text, longer than today's tagline).
  - `fields_config` (JSON): which fields to collect + required flags, e.g.
    `{"name":{"show":true,"required":true},"email":{...},"birthday":{...}}`.
    Ship with a validated default.
  - `qr_style` (JSON): `{"module_style":"square|rounded|dots","fg_color":...,
    "logo":true|false,"frame":"none|scan_to_join|collect_stamps"}`.
  - Links: `terms_url`, `privacy_url` (URL, blank ok).
  - `hide_powered_by` (bool) — only honored when `custom_branding` is on.

### Rendering deps (decision)
- Add **Pillow** + use **`qrcode[pil]`** `StyledPilImage` (module drawers +
  centre logo) — `qrcode` is already a dep, this is the smallest delta. Keep the
  SVG path for the web preview; render **PNG** for embedding into the poster.
- Poster PDF: render with **Pillow → PDF** (compose cover/logo/QR/reward text on
  a canvas, save as PDF) to avoid pulling in reportlab/weasyprint. Store to the
  configured `STORAGES` (local `MEDIA_ROOT` in dev, S3 in prod) and return a URL.
- Pin the new deps in `requirements.txt`; note them in the phase commit.

### Services
- `branding/services.py` → `resolve_theme(merchant, card=None)`: card-scoped row
  → merchant default → hard-coded system default. Apply entitlement gating:
  **without `custom_branding`**, force the default template + show "Powered by
  Stampn" (ignore `hide_powered_by`, cover image, custom fonts) — free plans keep
  a clean stock look; paid plans get the full theme.
- `branding/qr.py` → `render_qr_svg(join_url, qr_style)`,
  `render_qr_png(...)`, `render_poster_pdf(theme, card, join_url)`.

### Endpoints
- **Extend** `GET /enroll/{token}` (`enrollment/views.py`) to return the resolved
  theme block (template, colors, cover url, welcome body, resolved
  `fields_config`, terms/privacy, `show_powered_by`) alongside today's payload.
- **Extend** `GET /cards/{id}/qr` (`dashboard/views.py`) to render `qr_svg` from
  the resolved `qr_style` and to populate the real `poster_pdf_url`.
- **New** dashboard endpoints (owner/manager RBAC, tenancy-scoped):
  - `GET/PATCH /settings/enroll-theme` — merchant default theme.
  - `GET/PATCH /cards/{id}/enroll-theme` — per-card override (create/clear).
  - `POST /settings/enroll-theme/cover` (+ card variant) — image upload, with
    size/type/dimension validation.

### Tests (`backend/tests/`)
- Model + migration smoke; `unique_together`.
- `resolve_theme`: card override beats default beats system default.
- Entitlement gating: free plan can't unlock branded theme / hidden powered-by.
- QR render: styled SVG differs from default; PNG + poster PDF produced.
- Enroll endpoint returns theme; QR endpoint returns non-empty `poster_pdf_url`.
- Tenancy: merchant A can't read/patch merchant B's theme or card.
- Upload validation rejects oversized / non-image files.

### Definition of done
Migrations apply; new deps pinned; all endpoints documented in the DRF schema;
full quality gate green; no `core` change.

---

## Phase 2 — Registration Theme & QR: dashboard editor + live enroll page

**Goal.** Let the merchant edit the theme with a live preview, and make the
public join page render it.

**Depends on:** Phase 1 endpoints.

### Frontend — dashboard (`frontend/dashboard`)
- New settings screen **"Registration page & QR"** (new feature dir
  `src/features/enroll-theme/`, linked from `settings`):
  - Form for template, colors (pickers), font, welcome body, field toggles,
    terms/privacy URLs, cover-image upload, and the QR style
    (module style, logo on/off, frame).
  - **Live preview** panel: renders the enroll page + the QR side-by-side as the
    merchant edits (reuse the enroll page's presentational components).
  - Per-card override tab: "use merchant default" vs "customize this card".
  - Entitlement-aware: lock the rich controls behind `custom_branding` with an
    upgrade nudge (mirror existing gated UI).
- Poster button downloads the **server** `poster_pdf_url` (drop the browser
  print-to-PDF fallback once wired).

### Frontend — enroll (`Enroll.jsx`)
- Consume the theme from `GET /enroll/{token}`: apply template/colors/font/cover,
  render only the configured fields with their required flags, use custom
  terms/privacy links, honor `show_powered_by`. Keep AR/EN toggle + Google Wallet
  button. Fall back cleanly to today's look when no theme is set.

### Tests
- Component/interaction tests for the editor (field toggles, entitlement lock).
- Enroll page renders each template + respects `fields_config` required flags.
- `eslint --max-warnings 0` + `vite build` + `prettier` green on both frontends.

### Definition of done
Merchant can fully brand the page + QR and see it live; the public page reflects
it; free plans see the gated default.

---

## Phase 3 — Merchant Dashboard hardening

**Goal.** Close the smaller merchant-side gaps that don't need the theme work.

- **Frontend Sentry in `frontend/dashboard`** — mirror the admin Phase-15 setup:
  add `@sentry/react`, init in `main.jsx` guarded by `VITE_SENTRY_DSN`, tag
  `app:merchant-dashboard`, capture the router + query errors. Document the env
  vars. (No-op locally when the DSN is unset.)
- **Customer CSV export** — verify the endpoint + `entitlements.check(merchant,
  "export")` gate exist and are correct; wire/confirm the **Export** button in the
  customers UI; add a test for the gate + a small export.
- **Logo-in-QR-centre + server poster PDF** (moved here from Phase 1) — add
  **Pillow** + `qrcode[pil]`; render a styled **PNG** (module drawers + centre
  logo) and compose the poster (cover/logo/QR/reward text) to PDF; populate
  `poster_pdf_url` on `GET /cards/{id}/qr`. **Depends on the prod-media fix
  below** — otherwise the URL 404s in prod.
- **Prod media serving** — today `config/urls.py` serves `/media` only under
  `DEBUG`, so uploaded logos/covers/posters 404 in prod. Fix it (WhiteNoise media
  route or S3 `STORAGES`) so cover images + posters actually load in prod.

### Definition of done
Dashboard errors reach Sentry when a DSN is set; export works and is gated;
posters + cover images load in prod; both frontends pass their gate.

---

## Phase 4 — Admin panel deferrals

**Goal.** Ship the two features postponed from Phase 11.

- **Partner / affiliate tracking + payout report** — model
  (partner, referred-merchant link, attribution, commission), an admin screen to
  view partners + a payout report (period → owed), and the `/api/admin/v1/*`
  endpoints. Audit-logged, RBAC-gated (Finance/Super-admin), cursor-paginated.
- **Promotion grouping model** — a campaign/group wrapper over the individually
  shipped coupons (group → many coupons; group-level status + reporting).
  Migrate existing coupons to an optional group.

### Tests
Model + migration, RBAC (only Finance/Super-admin), tenancy/audit completeness,
report math. Backend gate green; admin frontend gate green.

---

## Phase 5 — Cross-cutting backend hardening

**Goal.** Observability + performance + contract accuracy.

- **Structured logging** — add a JSON `LOGGING` config (none exists today) with a
  request-ID filter (middleware that stamps/propagates an `X-Request-ID`), so logs
  are queryable. Wire Sentry to attach the request ID.
- **DB index review** — profile the cross-tenant admin analytics aggregates
  (revenue, platform, lifecycle) and the heaviest merchant list queries; add
  indexes where a query is slow. (Load-test hook for the launch checklist.)
- **OpenAPI contract sync** — fold the additive changes into frozen
  `contracts/openapi.yaml` on the next bump: `/loyalty/scan`, `Card.single_use`,
  `Card.referral_enabled`, `card_type`, `specialized_roles` + `custom_branding`
  entitlements, branded-enroll + **new theme** fields, and **all
  `/api/admin/v1/*` console endpoints (Phases 2–15)**. Reconcile against the live
  drf-spectacular schema at `/api/schema`; add a CI check for drift.

### Definition of done
JSON logs with request IDs in prod; no slow analytics query at target volume;
`openapi.yaml` matches the served schema; gate green.

---

## Phase 6 — Housekeeping & operational decisions

**Goal.** Resolve the kept-but-dormant integrations and finish the runbooks.

- **WhatsApp** — decide revive-or-remove; if remove, delete the dormant code +
  settings + tests and note it; if revive, spec its own phase. (Currently
  disabled on every plan.)
- **Fawry** — same decision (adapter + webhook kept but disabled, Paymob-only).
- **Secret-rotation runbook** — document rotating wallet / gateway / JWT keys
  (extends the existing admin incident runbook to a general secrets runbook).
- **Backup cron confirmation** — verify the nightly `backup.sh` + weekly
  `verify_backup.sh` crontab lines are installed on the box (or add them);
  document.
- **MFA enrolment confirmation** — confirm every real `AdminUser` has completed
  forced enrolment post-deploy (owner task; track here).

### Definition of done
Each integration has a recorded decision + action; runbook + backup lines in
place; MFA roster confirmed.

---

## Phase 7 — Tiered cards (silver / gold) — larger, deferred

**Goal.** Lifetime-accrual → membership tiers with per-tier perks. Touches the
core card model + both wallet builders + redemption logic, so it's a standalone
future phase, not bundled. Spec in full before starting (it may require a `core`
contract bump — treat carefully).

---

## Not build phases — tracked externally

**Awaiting external approval (can't close from code):**
- **Apple Wallet passes** — code + tests done, off in prod; needs Apple Developer
  account + Pass Type ID cert. On approval: provision cert secrets, set
  `APPLE_PASS_CERT_*`, show the Apple button on iOS, real-iPhone smoke test.
  (Apple hero/banner image wiring folds in here.)
- **Paymob go-live** — adapter + idempotent webhooks built (stub mode); needs a
  live merchant-account round-trip.

**Owner / infra launch tasks (`main/docs/Admin-Launch-Checklist.md`):**
- Edge IP-allowlist activation, `VITE_SENTRY_DSN` for the admin build, manual
  pentest, `pip-audit` + `npm audit`, backup-restore test, analytics load-test,
  access-token-lifetime decision, eng-lead sign-off.

**Real-device / real-service verification sweep** — scan→stamp→Google Wallet on a
real phone; points balance; single-use expiry; wallet-message notification;
referral bonus; branded enroll; scheduled campaign firing (Celery beat).
Needs a live environment; run alongside Phase 2/3.

---

## Suggested execution order

1. **Phase 1** (theme + QR backend) → 2. **Phase 2** (editor + enroll page) →
3. **Phase 3** (dashboard hardening) → 4. **Phase 5** (logging/index/contract —
pairs well after new endpoints exist) → 5. **Phase 4** (admin deferrals) →
6. **Phase 6** (housekeeping) → 7. **Phase 7** (tiers, when prioritized).

External-approval + owner items proceed in parallel as approvals land.
