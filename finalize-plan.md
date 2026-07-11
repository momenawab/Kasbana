# Stampn / Kasbana — Finalize Plan

> Snapshot **2026-07-10**, branch `dev`. This is the single consolidated plan for
> shipping the project. It supersedes the overlapping snapshots in
> [`main/docs/MISSING.md`](./main/docs/MISSING.md) (stale, 2026-07-01) and folds
> the still-open items from [`finalize-missing.md`](./finalize-missing.md) +
> [`finalize-phases.md`](./finalize-phases.md) (Phases 1–3 shipped) into one list.
>
> Two **new** features are specced in full here and take priority:
> **Phase A — Main QR** and **Phase B — Merchant support**.

---

## Context — why this document exists

The product is functionally complete and deployed: core loyalty, both wallets,
the merchant dashboard, and all 15 admin-panel phases are live. What remains is
(a) two features the team wants before launch, (b) a handful of hardening and
housekeeping items, and (c) things that cannot be closed from code because they
wait on Apple/Paymob approval or on an owner running a checklist.

The three existing markdown files disagree with each other because each was a
snapshot at a different date, and none of them mention the two new features.
This file is the current truth.

### Ground rules (unchanged, apply to every phase)

- **`core` is frozen.** No migrations on `core.*`. New models live in their
  owning app or a new app. This directly shapes Phase A: `core.Card` and
  `core.EnrollmentToken` cannot gain a column.
- **Blank = default.** Every unset field falls back to today's behavior.
- **Best-effort rendering.** A QR/poster/render failure must never withhold the
  underlying resource — wrap in `try/except` like `branding/poster.py` and
  `wallets/google/hero.py` already do.
- Backend gate: `ruff` + `black` + `mypy` + `drf-spectacular` + `pytest` green.
  Frontend gate: `eslint --max-warnings 0` + `prettier --check` + `vitest run` +
  `vite build` green.
- Work on `dev`; promote to `prod` with `git merge --no-ff` only when green and
  the user approves.

---

# Phase A — Main QR (print once, switch the card anytime) 🎯 ✅ DONE

> **Status: built on `dev`.** New `enrollment.MerchantEnrollLink` model +
> migration `0002`, `resolve_join_target` replacing `resolve_active_token` in
> `EnrollView`, the three `/settings/main-qr` endpoints, and the dashboard
> `/main-qr` screen + "Set as main" on the cards grid. **26 new tests; full gate
> green** (backend 576 pytest · ruff · black · mypy; frontend eslint 0 warnings ·
> 46 vitest · vite build · prettier).
>
> **Two problems found and fixed during the build that the plan hadn't
> anticipated:**
> - `branding.poster.build_and_store_poster` named every poster
>   `card_{id}_{digest}.pdf` and pruned its siblings. The main-QR poster renders
>   the *same card* at a *different join URL*, so the two would have deleted each
>   other's file on every request. It now takes a `key` argument; the main QR
>   passes `main_{merchant.id}`. Covered by a regression test.
> - Adding "Main QR" to the sidebar would have pushed **Campaigns** out of the
>   mobile bottom bar (it renders the first 5 visible items). Nav items now carry
>   an optional `mobile: false` flag; the main QR is desktop/tablet-only in the
>   bottom bar, and the mobile bar is unchanged.
>
> Also extracted `dashboard/qr_assets.py::build_qr_assets` so the card QR and the
> main QR share one best-effort render path instead of duplicating it.

## The problem

Every QR today is **per-card**. `core.EnrollmentToken`
(`backend/core/models.py:227`) binds one random token to exactly one `Card`, and
`GET /cards/{id}/qr` (`backend/dashboard/views.py:218`) builds
`join_url = {ENROLL_BASE_URL}/enroll/{token}` from it. So a merchant running two
programs, or wanting to swap which program new customers join, must **print a new
QR every time**. There is no merchant-level QR and no notion of a "main" card —
grep for `is_main` / `is_primary` / `default_card` returns nothing.

## The solution

A **permanent, merchant-level token** that resolves to whichever card the
merchant has elected as **main**. The merchant prints that QR once; changing the
main card re-points the same printed QR at a different program. Per-card QRs keep
working exactly as they do today.

### A.1 — New model (`backend/enrollment/models.py`)

`core` is frozen, so the merchant token and the main-card pointer cannot live on
`Card` or `EnrollmentToken`. Put both on one new row in the **non-frozen**
`enrollment` app, next to the existing `Referral` model:

```python
class MerchantEnrollLink(UUIDModel, TimeStampedModel):
    """The merchant's permanent join QR. Re-points at a different Card without
    changing the token, so a printed poster never goes stale."""
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE,
                                    related_name="enroll_link")
    token = models.CharField(max_length=32, unique=True, db_index=True)
    primary_card = models.ForeignKey(Card, null=True, blank=True,
                                     on_delete=models.SET_NULL,
                                     related_name="+")
    is_active = models.BooleanField(default=True)
```

- `primary_card` is `SET_NULL`: deleting the main card must not delete the link.
- One row per merchant, created lazily (see `get_or_issue_merchant_link` below).
- Token generation reuses `enrollment/tokens.py:_generate_token()`.

### A.2 — Resolution (`backend/enrollment/tokens.py`)

Keep **one public route** (`/enroll/{token}`) so the enroll page, referral links,
and the frontend need no new URL shape. Add a resolver that tries the card token
first, then the merchant link:

```python
def get_or_issue_merchant_link(merchant: Merchant) -> MerchantEnrollLink: ...

def resolve_join_target(token: str) -> tuple[Merchant, Card] | None:
    """Card token → its card. Merchant token → its primary_card."""
```

Rules, each of which needs a test:

- A merchant token whose `primary_card` is `None` → **404** (same as an unknown
  token). Never guess a card.
- A merchant token whose `primary_card.status != ACTIVE` → **404**. A DRAFT or
  ARCHIVED program must not accept joins through the main QR.
- An inactive link (`is_active=False`) → **404**.
- Card-token behavior, including `TokenExpired` → 410, is unchanged.

`EnrollView` (`backend/enrollment/views.py:32`) switches from
`resolve_active_token` to `resolve_join_target`. Both `GET` and `POST` use only
`row.card` / `row.merchant`, so the change is contained. The referral URL at
`views.py:140` keeps using the incoming `token`, which means **referral links
minted from the main QR stay on the main QR** — correct, and worth a test.

### A.3 — Endpoints (`backend/dashboard/`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/settings/main-qr` | `{ token, join_url, qr_svg, poster_pdf_url, primary_card }` |
| `PATCH` | `/settings/main-qr` | `{ primary_card_id }` — elect the main card |
| `POST` | `/settings/main-qr/rotate` | mint a fresh token (invalidates printed posters — confirm in UI) |

- Permission: `CanManageCards` (owner/manager), tenancy-scoped via `get_scoped`.
- `PATCH` validates the card belongs to the merchant **and** is `ACTIVE`.
- Rendering reuses the existing helpers, no new deps:
  `branding.services.resolve_theme(merchant, card=primary_card)` →
  `branding.qr.render_qr_svg(join_url, theme["qr_style"])` →
  `branding.poster.build_and_store_poster(...)`. Wrap both in the same
  best-effort `try/except` that `CardQRView` uses so a poster failure still
  returns `qr_svg`.

### A.4 — Frontend (`frontend/dashboard/src/`)

- **`features/cards/CardsList.jsx`** — a `Main` badge on the elected card, and a
  "Set as main" action on every other **active** card. Disabled with a tooltip on
  draft/archived cards.
- **New `features/main-qr/MainQr.jsx`** at route `/main-qr`, linked from the
  sidebar (`layout/Sidebar.jsx`) and from `EnrollQr.jsx`. It reuses
  `components/QrBlock.jsx` (PNG download) and the server `poster_pdf_url`, shows
  the join URL with copy-to-clipboard, and states plainly: *"Print this once.
  Changing your main card re-points this QR — no reprint needed."*
- **Rotate** sits behind a confirm dialog that names the consequence (existing
  printed posters stop working).
- i18n: new `mainQr.*` keys in `locales/en.json` + `ar.json`.

### A.5 — Tests

Backend (`backend/tests/`): model + migration smoke; `get_or_issue_merchant_link`
is idempotent; `resolve_join_target` for card-token / merchant-token / null
primary / non-active primary / inactive link; `PATCH` rejects a foreign card and
a draft card; tenancy (merchant A cannot read or patch B's link); rotate changes
the token and 404s the old one; a full join through the merchant token creates a
`CustomerCard` on the right program; referral URL minted from a merchant token
points back at the merchant token.

Frontend: `CardsList` shows the badge and disables the action on inactive cards;
`MainQr` renders the empty state when no main card is set.

### Definition of done

A merchant sets a main card, prints one QR, switches the main card, and the
**same** printed QR joins customers to the new program. Per-card QRs unchanged.

---

# Phase B — Merchant support (dashboard → admin Support tab) ✅ DONE

> **Status: built on `dev`.** `console.ContactMessage` gained nullable `merchant`
> + `source` fields (migration `0012`); new dashboard `GET/POST /support/messages`
> (`dashboard/views_support.py`, identity from the session, `support_message`
> throttle scope), new admin `GET /merchants/{id}/support/messages`
> (`views_support.py`); dashboard `/support` screen + sidebar entry; admin
> `SupportTab` "Messages from merchant" thread with reply; global `MessagesHome`
> gained a source filter + merchant chip. **13 new tests; full gate green**
> (backend 599 pytest · ruff · black · mypy; both frontends eslint 0 warnings +
> build; dashboard 46 vitest). Verified end-to-end at runtime: a merchant sent a
> message, it appeared on the admin per-merchant list **and** the global inbox
> tagged `dashboard`/merchant, a support admin replied (branded email rendered,
> `To: shop@sup.com`), and the merchant's status flipped to `replied`.
>
> **Probes that held:** a spoofed `email`/`name`/`merchant` in the POST body is
> ignored (identity comes from the session); a merchant JWT is rejected from the
> admin route (401); empty body → 400; the throttle blocks the 11th POST in a
> minute (10×201 then 429); the marketing intake still defaults to
> `source=marketing`, `merchant=null`.
>
> **Not browser-driven:** the admin `SupportTab` UI itself was verified by build +
> its endpoints via curl, not a Playwright pass (admin login is MFA-gated); the
> dashboard `/support` screen *was* driven in a real browser.

## The problem

Support is one-directional. The admin has a full support console —
impersonation, support notes, password reset, resend invite, clear stuck
checkout (`backend/console/views_support.py`, `frontend/admin/src/features/
merchants/SupportTab.jsx`) — and a public contact form on the marketing site
(`frontend/src/pages/Support.jsx` → `POST /contact` →
`console.public.PublicContactCreateView` → `ContactMessage`).

But a **logged-in merchant has no way to reach support at all**. The only
"support" string in the dashboard is a fallback label on the impersonation
banner (`layout/Shell.jsx:58`).

## The solution

Reuse the existing `ContactMessage` model, status lifecycle, and branded email
reply. Merchant-submitted messages surface **in the admin panel on that
merchant's Support tab**, next to the support notes — not buried in the global
Messages inbox.

### B.1 — Model change (`backend/console/models.py`)

`ContactMessage` (line 446) is in the non-frozen `console` app. Add two nullable
fields so existing rows are untouched:

```python
merchant = models.ForeignKey("core.Merchant", null=True, blank=True,
                             on_delete=models.SET_NULL,
                             related_name="contact_messages")
source = models.CharField(max_length=16, choices=Source.choices,
                          default=Source.MARKETING)   # marketing | dashboard
```

Existing rows backfill to `source="marketing"`, `merchant=None` — exactly what
they are. One migration, additive, no data loss.

### B.2 — Merchant endpoints (`backend/dashboard/`)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/support/messages` | authenticated; creates a `ContactMessage` with `merchant=request.merchant`, `source="dashboard"` |
| `GET` | `/support/messages` | this merchant's own messages + statuses |

- Name/email are taken from the authenticated user, **not** the request body —
  a merchant must not be able to spoof another sender. Body carries only
  `subject` + `message`.
- No honeypot needed (authenticated), but keep a throttle scope so a compromised
  account cannot flood the queue.
- **Tenancy:** `GET` filters on `merchant=request.merchant`. Add a test that
  merchant A cannot see B's messages.

### B.3 — Admin side (`backend/console/`, `frontend/admin/`)

- `GET /merchants/{id}/support/messages` — this merchant's `ContactMessage`
  rows, in `views_support.py`, gated by the existing `IsSupportAdmin`.
- **`SupportTab.jsx`** gains a "Messages from merchant" thread above the notes
  thread: subject, body, status chip, and a **Reply** action that reuses the
  existing `ContactReplyView` + the branded `templates/email/contact_reply.html`.
- The global `MessagesHome.jsx` inbox gains a `source` filter and shows a
  merchant chip on dashboard-originated rows, so nothing gets lost if support
  works the global queue instead.
- Replies are audit-logged through the existing `console.audit.record`.

### B.4 — Frontend (`frontend/dashboard/src/`)

- New `features/support/Support.jsx` at `/support`, linked from the sidebar:
  subject + message form, list of the merchant's past messages with status
  (`new` / `read` / `replied`), and a note that replies arrive by email.
- Success/failure toasts via the existing `hooks/useToast.jsx`.
- i18n: `support.*` keys in `en.json` + `ar.json`.

### B.5 — Tests

Backend: `POST /support/messages` sets `merchant` + `source` and **ignores** a
spoofed `email` in the body; `GET` is tenancy-scoped; the admin per-merchant list
is `IsSupportAdmin`-gated; reply marks `replied_at` and sends one email;
migration backfills `source="marketing"` on existing rows.

Frontend: dashboard support form submits and renders the returned list; admin
`SupportTab` renders the thread and the reply action.

### Definition of done

A merchant sends a message from the dashboard; it appears on that merchant's
admin Support tab; a support admin replies; the merchant receives the branded
email and sees the status flip to `replied`.

---

# Phase C — Wallet pass templates

Fully specced already in [`wallet-templates-plan.md`](./wallet-templates-plan.md)
(a layout-locked template gallery over the existing freeform `WalletCardDesign`
editor). **Not started.** Read that file cold; it is self-contained. Slot it here
because it is merchant-visible polish, not hardening.

---

# Phase D — Cross-cutting backend hardening ✅ DONE

> **Status: built on `dev`.** All three sub-tasks landed. **9 new tests; full
> gate green** (backend 608 pytest · ruff · black · mypy · schema 0 errors; new
> `check_openapi` CI step in sync). Runtime-verified: JSON logs carry
> `request_id` + `extra=` fields under `LOG_FORMAT=json`, the `X-Request-ID`
> header is minted + echoed (and an inbound one reused), and both index
> migrations apply to a real DB.
>
> **What shipped:**
> - **Structured logging** — new `common/logging.py` (dependency-free
>   `JSONFormatter` + `RequestIDFilter` + a `request_id` `ContextVar`), a
>   `RequestIDMiddleware` placed first in the chain (reuses/mints `X-Request-ID`,
>   caps it at 64 chars, tags the Sentry scope, echoes it on the response), and a
>   `LOGGING` config in `base.py`. Env-controlled `LOG_FORMAT` (`console` default;
>   prod defaults to `json`).
> - **DB indexes (console/billing only, per decision)** — `billing.Invoice`
>   gained `(status, issued_at)` for the cross-tenant revenue scans (the existing
>   `(merchant, -issued_at)` can't serve them); `billing.Subscription` gained
>   `(status)` for the platform status counts. Migration `billing/0011`.
>   **Frozen-core findings, noted not touched:** `core.StampLedger` would benefit
>   from `(event_type)` and `(merchant, created_at)` indexes for the platform
>   analytics `.filter(event_type=…)` and `.values("merchant").annotate(Max)`
>   queries — deferred because `core` is frozen.
> - **OpenAPI contract sync (generate-from-code, per decision)** — made
>   drf-spectacular the source of truth. Fixed the schema-gen errors
>   (`WalletTemplateListView`, `AccountExportView` had no response serializer;
>   schema now generates with **0 errors**), regenerated `contracts/openapi.yaml`
>   from the live code (1700 curated lines → 8368 generated, now covering all 83
>   `/api/admin/v1/*` operations + the Phase A/B endpoints, bumped to `1.2.0`),
>   and added a `console` management command **`check_openapi`** (`--write` to
>   regenerate, default to diff-and-fail) wired as a **CI drift step** in
>   `backend-ci.yml`. Generation confirmed deterministic across runs.

---

# Phase E — Admin panel deferrals

- **Partner / affiliate tracking + payout report** — deferred from Phase 11.
  Model (partner, referred-merchant link, attribution, commission), an admin
  screen, `/api/admin/v1/*` endpoints. Audit-logged, RBAC-gated to
  Finance/Super-admin, cursor-paginated.
- **Promotion grouping model** — deferred from Phase 11. A group wrapper over the
  individually-shipped coupons; migrate existing coupons to an optional group.

---

# Phase F — Housekeeping & operational decisions

- **WhatsApp** — dormant, disabled on every plan. Decide: revive or delete.
- **Fawry** — adapter + webhook kept but disabled (Paymob-only). Same decision.
- **Secret-rotation runbook** — document rotating wallet / gateway / JWT keys.
  The admin incident runbook exists; a general secrets runbook does not.
- **Backup cron confirmation** — verify the nightly `backup.sh` + weekly
  `verify_backup.sh` crontab lines are actually installed on the box.
- **MFA enrolment confirmation** — confirm every real `AdminUser` completed
  forced enrolment post-deploy.
- **Stale docs** — after this file lands, delete or redirect `main/docs/MISSING.md`
  and `finalize-missing.md` so there is one source of truth.

---

# Phase G — Tiered cards (silver / gold) — deferred, largest

Lifetime accrual → membership tiers with per-tier perks. Touches the **frozen
`core` card model**, both wallet builders, and redemption logic, so it may
require a `core` contract bump. Spec in full before starting. Do not bundle.

---

# Not build phases — tracked externally

**Awaiting external approval (cannot be closed from code):**

- **Apple Wallet** — code path complete and tested, but off in prod
  (`apple_pass_url` is null; the enroll page shows only Google Wallet). Needs an
  Apple Developer account + Pass Type ID cert (`pass.p12` + WWDR). On approval:
  provision the cert into secrets, set `APPLE_PASS_CERT_*`, show the Apple button
  on iOS, real-iPhone smoke test (register → APNs push → pass pull → stamp
  update). The **Apple hero/strip image** wiring folds in here.
- **Paymob go-live** — adapter + idempotent webhooks built, running in stub mode.
  Needs one live trial → paid → cancel round-trip.
- **Pricing plans** — need to be finalized and published on the marketing site.

**Owner / infra launch tasks** — see
[`main/docs/Admin-Launch-Checklist.md`](./main/docs/Admin-Launch-Checklist.md):
edge IP-allowlist activation, `VITE_SENTRY_DSN` for the admin **and** dashboard
builds, manual pentest, `pip-audit` + `npm audit`, backup-restore test, analytics
load-test, access-token-lifetime decision, eng-lead sign-off.

**Real-device / real-service verification sweep** — much has shipped with unit
tests but never been confirmed live. Before onboarding a real merchant, walk each
of these on a real phone against real services:

- [ ] Scan → stamp → Google Wallet pass updates
- [ ] Points card: scan → add N points → wallet shows the new balance
- [ ] Single-use card: redeem → pass expires (Google `EXPIRED`)
- [ ] Free wallet message / campaign lands as a notification
- [ ] Referral: friend joins via `?ref=` → both get the bonus stamp
- [ ] Branded enrollment: custom copy shows, "Powered by" hidden
- [ ] Specialized roles: Marketing / Designer see only their area
- [ ] Scheduled campaign fires at `schedule_at` (needs Celery beat running)
- [ ] **Phase A:** join through the main QR, then switch the main card and join
      again — same printed QR, different program
- [ ] Authenticated customer CSV export downloads
- [ ] A generated poster PDF opens from `/media` in prod

---

# Suggested execution order

1. **Phase A** (Main QR) — self-contained, highest merchant value.
2. **Phase B** (Merchant support) — self-contained, needed before onboarding.
3. **Phase D** (hardening + contract sync) — pairs naturally right after A and B
   add endpoints, so the OpenAPI sync happens once.
4. **Phase C** (wallet templates) — polish, independent.
5. **Phase E** (admin deferrals) → 6. **Phase F** (housekeeping) →
   7. **Phase G** (tiers, when prioritized).

External-approval and owner items proceed in parallel as approvals land. The
real-device sweep runs alongside Phase A/B on a live environment.

---

# For reference — what IS done and live

**Merchant side:** core loyalty (enroll, stamp, redeem, Google Wallet), cashier
Scan/Till, dashboard (cards, customers, analytics, campaigns, automations,
locations, team, billing, settings), 5-role RBAC, Paymob billing + idempotent
webhooks, free wallet messaging, scheduled campaigns, advanced segments, poster
PDF, single-use cards, referrals, points cards, rate-limiting, off-box backups,
registration-page themes + styled QR (finalize Phases 1–3), browser Sentry,
customer CSV export, logo-in-QR + server poster PDF.

**Admin side (all 15 phases, live):** auth/audit spine, merchant directory,
DB-backed plan catalogue, subscription management, billing/invoices, support
tools + impersonation, revenue + platform analytics, lifecycle + moderation,
communications/announcements, coupons/promotions, admin team + RBAC matrix,
audit-log viewer + PDPL compliance, platform ops (health, flags, maintenance,
monitors), security hardening (TOTP MFA, sessions + rotation, step-up, lockout,
Sentry).

**~472 backend tests green.** Backend + both frontends deploy in lockstep from
`prod`. Google Wallet live; Sentry live on backend, admin, and dashboard.
