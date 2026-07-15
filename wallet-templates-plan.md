# Plan — Wallet Pass **Templates** (fixed-layout, merchant-customizable)

> **Audience:** the implementing agent (GLM 5.2). This is a self-contained build
> plan — read it cold and implement. It extends the existing **freeform** wallet
> pass editor with a **template** system (AddToWallet.co-style): a gallery of
> pre-designed, layout-locked passes where the merchant only edits colors,
> stamp icons, a bottom image, and text — never field positions.

---

## 1. Goal (what & why)

Today the merchant designs a pass **field-by-field** (`WalletDesignEditor` +
`WalletCardDesign`) — powerful but easy to make ugly. Merchants asked for
**ready-made templates** they can pick and lightly customize.

A **template** is a **code-defined, layout-locked** pass design. The template
author fixes *where every field sits*; the merchant can only change:

- **Colors** — background, foreground/text, field-label tint, stamp-strip band.
- **Stamp icons** — the filled and unfilled (empty) stamp images.
- **A bottom image** — the full-width photo shown on image-style templates.
- **Text content** — the values that fill the template's fixed slots (headline,
  reward text, etc.), and the logo.

The merchant **cannot** move fields, add/remove slots, or change positions.

### Reference

The three WhatsApp screenshots in the repo root (AddToWallet.co gallery) are the
visual target. Note the two recurring bottom treatments:

- **Loyalty Pass** cards → a **stamp counter (row of icons) under the QR**.
- **Store Card / Event Pass / Gift Card** cards → a **full-width image under the
  barcode**.

---

## 2. THE core rule — Apple vs Google positioning

The **same template** renders on **both** Apple and Google, but the bottom
visual maps to a **different position per platform**, because Apple's storeCard
pins the barcode to the very bottom (nothing can go below it):

| Template `bottom_visual` | Google (flat card) | Apple (storeCard) |
|---|---|---|
| `stamps` (stamp counter) | stamp-grid image **under the QR** (hero/image module) | stamp grid in the **strip band at the TOP** (above primary) |
| `image` (photo) | full-width image **under the barcode** | image in the **strip band at the TOP** |
| `none` | — | — |

**"Apple will be upper"** = on Apple the image / stamp-counter lives in the strip
at the **top**; on Google it lives **below** the QR/barcode. Implement this exact
mapping — it is the crux of the feature.

Apple storeCard region order (top→bottom): `header` (top-right) · **`strip`
(top band)** · `primary` · `secondary` · `auxiliary` · `barcode` (bottom) ·
`backFields`. There is **no region below the barcode**, which is *why* the
bottom visual must move to the strip on Apple.

Google flat card order (top→bottom): header (logo + title + subtitle) ·
**`heroImage` band** · `loyaltyPoints` (balance) · `textModulesData` · barcode ·
(`imageModulesData` can render below). Put the bottom visual in the hero (for
`stamps`, we already do this) or an image module.

---

## 3. Current architecture (files you will touch)

**Backend** (`backend/wallets/`, Django app — `core.Card` is a FROZEN contract
model; never migrate it — all new state lives in `wallets`):

- `models.py` → `WalletCardDesign` (OneToOne `core.Card`). Already stores the
  freeform slots + colors + `strip_empty_url` / `strip_filled_url` /
  `strip_bg_color` / `google_stamp_hero`. **You add `template_key` +
  `bottom_image_url` here.**
- `design.py` → `resolve`/token helpers: `get_design(card)`,
  `field_context(cc)`, `render_slots(slots, ctx, prefix)`, `VALUE_TOKENS`
  (`balance|stamps|points|goal|remaining|reward|merchant|program` + `text:…`).
- `stamp_grid.py` → **shared** pure Pillow renderer
  `render_stamp_grid(earned, required, bg, fg, size, empty_icon, filled_icon)`
  + `hex_to_rgb`, `darken`, `load_icon`. Reuse for both platforms & for the
  bottom image compositing.
- `apple/passdata.py` → builds `pass.json` (fields, colors, logoText, barcode).
  Already honors `WalletCardDesign` per-region overrides + `label_color` +
  `apple_strip_enabled`. **Templates drive the fixed field layout here.**
- `apple/signing.py` → `build_pass_images(cc)` renders `icon/logo/strip` PNGs;
  `_render_stamp_strip` = `stamp_grid.render_stamp_grid`. Already tiles custom
  stamp icons + uses `strip_bg_color`. **`image` templates → render the bottom
  image into the strip here.**
- `google/builders.py` → `build_loyalty_class(card)` + `build_loyalty_object(cc)`.
  Already sets `textModulesData` and a stamp `heroImage` when `google_stamp_hero`.
  **Templates drive title/subtitle/rows + the bottom visual (hero/image module).**
- `google/hero.py` → `stamp_hero_url(cc)`: renders the stamp grid to a
  **content-addressed** PNG under `/media/google-hero/` and returns an absolute
  URL. **Google caches by URL → a new stamp count MUST yield a new URL.** Model
  a `bottom_image` hero the same way (content-address on the image + colors).
- `google/client.py` → `push_update(cc)` PATCHes the object (balance + hero) on
  each stamp. Keep the hero refreshed here for `stamps` templates.
- `serializers.py` → `WalletCardDesignSerializer` (add the new fields + validate
  `template_key` against the registry; reject positions the template doesn't
  allow).
- `views.py` → `CardWalletDesignView` `GET/PATCH /cards/{id}/wallet-design`
  (CanManageCards, tenancy-scoped, **PATCH gated by `custom_branding`**).
- `service.py` / `tasks.py` → `push_update` / `provision` seams (no change
  expected, but the hero refresh flows through here on stamp).

**Frontend** (`frontend/dashboard/src/`):

- `features/cards/WalletDesignEditor.jsx` → the current freeform editor (mounted
  in `features/cards/CardDesigner.jsx`, edit mode only). **Add a template gallery
  picker + a restricted "template mode" editor.**
- `components/WalletPreview.jsx` → faithful Apple storeCard + Google previews,
  already design-aware (reads `design`, renders strip/hero, tokens). **Extend to
  render each template's fixed layout + the bottom image.**
- `features/cards/api.js` → `useWalletDesign(id)` / `useSaveWalletDesign(id)`.
- `hooks/usePlan.js` → `can('custom_branding')` / `requireFeature(...)` gating.
- `locales/en.json` + `locales/ar.json` → i18n (add `walletTemplates.*`).
- Uploads use the shared `components/FileUpload` → `POST /uploads` (returns a
  `/media/...` URL string, like `logo_url`).

---

## 4. Data model

Add to `wallets.models.WalletCardDesign` (new migration in `wallets/migrations/`,
**not** `core`):

```python
# Which template drives the layout. "custom" = today's freeform editor
# (unchanged). Any other key selects a code-defined, layout-locked template.
template_key = models.CharField(max_length=40, default="custom")

# Full-width bottom image for image-style templates (uploaded via /uploads).
bottom_image_url = models.URLField(blank=True)
```

Reuse existing fields for the editable variables: `color_bg`/`color_fg` live on
`core.Card`; `label_color`, `strip_bg_color`, `strip_empty_url`,
`strip_filled_url` already exist. Text content reuses the card's own
`name`/`reward_title`/`reward_description` + tokens (do **not** duplicate).

> **Design decision:** `template_key == "custom"` → render exactly as today
> (freeform slots). `template_key` in the registry → **ignore the freeform slots**
> and render from the template definition + editable variables. This keeps the
> existing feature intact and adds templates as a parallel, cleaner path.

---

## 5. Template registry (code-defined)

New module `wallets/templates.py`. A pure dict registry — no DB, no user-created
templates (positions are locked by design). Each entry declares the fixed layout
for **both** platforms and which variables are editable.

```python
# wallets/templates.py
TEMPLATES: dict[str, dict] = {
  "loyalty_stamps": {
    "name": "Loyalty — stamps",
    "card_types": ["STAMP"],
    "bottom_visual": "stamps",           # stamps | image | none
    "editable": ["color_bg", "color_fg", "label_color",
                 "strip_bg_color", "strip_empty_url", "strip_filled_url",
                 "logo"],
    # Apple: fixed field sources per region (value tokens from design.VALUE_TOKENS
    # or "text:<literal>"). Strip carries the stamp grid (top).
    "apple": {
      "header":    [{"label": "STAMPS", "source": "balance"}],
      "primary":   [],
      "secondary": [{"label": "REWARD ON {goal} VISITS", "source": "reward"}],
      "auxiliary": [],
    },
    # Google: title/subtitle/rows fixed; bottom visual = stamp hero (under QR).
    "google": {
      "title": "merchant", "subtitle": "program",
      "rows": [{"label": "Reward", "source": "reward"}],
    },
  },
  "store_image": {
    "name": "Store card — image",
    "card_types": ["STAMP", "POINTS"],
    "bottom_visual": "image",
    "editable": ["color_bg", "color_fg", "label_color", "bottom_image_url", "logo"],
    "apple":  {"header": [{"label": "POINTS", "source": "balance"}],
               "primary": [{"label": "REWARD", "source": "reward"}],
               "secondary": [], "auxiliary": []},
    "google": {"title": "merchant", "subtitle": "program", "rows": []},
  },
  # Add 4–6 starter templates spanning the reference categories:
  #   loyalty_stamps, store_image, membership_minimal, event_image,
  #   giftcard_image, coffee_stamps … (keep names + editable lists tight).
}

def get_template(key: str) -> dict | None:
    return TEMPLATES.get(key)
```

Keep it small and boring. The registry is the single source of truth the backend
renderers **and** the frontend preview both read (expose it to the frontend — see
§7). Field `label` strings may contain `{goal}` etc. — interpolate from the card.

---

## 6. Backend implementation steps

1. **Model + migration** — add `template_key`, `bottom_image_url`;
   `makemigrations wallets` + `migrate`.
2. **`wallets/templates.py`** — the registry + `get_template`.
3. **`design.py`** — add `resolve_layout(card)`: if the design's `template_key`
   is a registry key, return the template's fixed Apple/Google layout with label
   `{…}` interpolation + token resolution; else return `None` (→ freeform path).
4. **Apple (`apple/passdata.py`)** — when a template is active, build
   `storeCard` fields from `template["apple"]` (ignore freeform slots). Keep
   using `label_color` + colors. Force `apple_strip_enabled=True` when
   `bottom_visual == "stamps"`.
5. **Apple images (`apple/signing.py`)** — when `bottom_visual == "stamps"`
   render the stamp grid into the strip (already works, reuse `stamp_grid`). When
   `bottom_visual == "image"`, render `bottom_image_url` into the strip band
   (top) — decode via the existing `_local_media_bytes`, fit to the strip size
   (1125×369 @3x), letterbox on `strip_bg_color`.
6. **Google (`google/builders.py` + `google/hero.py`)** — set title/subtitle/
   rows from `template["google"]`. For `bottom_visual == "stamps"` use the
   existing `stamp_hero_url` (content-addressed, per-count). For
   `bottom_visual == "image"` add a `google/hero.py` sibling
   `bottom_image_hero_url(cc)` that stores the merchant image content-addressed
   and sets it as `heroImage` (static per image; no per-count busting needed).
7. **`google/client.py`** — keep refreshing the hero in `push_update` for
   `stamps` templates (new count → new URL). No-op for `image` (static URL).
8. **Serializer/validation (`serializers.py`)** — accept `template_key` +
   `bottom_image_url`; validate `template_key` is `"custom"` or a registry key;
   when a template is set, only allow that template's `editable` variables to be
   written (reject/ignore others). Keep the existing `custom` path untouched.
9. **Endpoint** — no route change; `PATCH /cards/{id}/wallet-design` still gated
   by `custom_branding`.
10. **Tests (`backend/tests/test_wallet_design.py` + a new
    `test_wallet_templates.py`)** — cover: template selection drives Apple fields;
    `stamps` template puts the grid in the Apple strip (top) and a per-count
    Google hero (URL changes with count); `image` template puts the image in the
    Apple strip and a static Google hero; a non-editable variable is ignored;
    tenancy + `custom_branding` gating; `custom` path unchanged; field keys stay
    globally unique (Apple rejects duplicates — see the regression test already
    in `test_wallet_design.py::test_field_keys_are_globally_unique`).

---

## 7. Frontend implementation steps

1. **Expose the registry** — add a lightweight read of the template registry to
   the frontend. Two acceptable options: (a) a `GET /wallet-templates` endpoint
   returning `[{key,name,card_types,bottom_visual,editable,preview}]`, or (b) a
   mirrored JS constant in `features/cards/walletTemplates.js` kept in sync with
   `wallets/templates.py`. **Prefer (a)** so there's one source of truth.
2. **Template gallery picker** — in `WalletDesignEditor.jsx`, add a top section:
   a grid of template cards (mini `WalletPreview` per template, filtered by the
   card's type) + a "Custom (advanced)" option that reveals today's freeform
   editor. Selecting a template sets `design.template_key`.
3. **Restricted template editor** — when a template is selected, show **only**
   the template's `editable` controls: color pickers (bg/fg/label/strip),
   filled/unfilled stamp `FileUpload`s (for `stamps`), bottom-image `FileUpload`
   (for `image`), logo. Hide the freeform slot editors. Positions are not
   editable.
4. **Dual live preview (`WalletPreview.jsx`)** — render the selected template's
   fixed layout for **both** platforms, applying the Apple-vs-Google rule from
   §2: on Apple show the stamp grid / bottom image in the **top strip band**; on
   Google show it **under the QR/balance**. Reuse the existing `StampGrid` +
   `darkenHex` helpers already in the file.
5. **Save** — `useSaveWalletDesign` PATCHes `template_key` + the editable vars.
   On a free plan keep the `custom_branding` gate + upgrade nudge (existing).
6. **i18n** — add `walletTemplates.*` keys to `en.json` + `ar.json` (template
   names, "Choose a template", "Custom (advanced)", editable-field labels,
   bottom-image/stamp-icon labels). Mirror the existing `walletDesign.*` style.

---

## 8. Constraints & conventions (do not violate)

- **`core` is frozen** — no migrations on `core.*`. All new fields live on
  `wallets.WalletCardDesign`.
- **Blank = default** — every unset variable must fall back to today's smart
  default so an un-templated card is unchanged.
- **Apple duplicate field keys are fatal** — every `key` must be unique across
  the whole pass or iOS shows *"Safari cannot download this file"*. Namespace
  keys per region (`h/p/s/x/b…`) exactly like `render_slots(..., prefix)`.
- **Google caches images by URL** — stamp heroes MUST be content-addressed per
  count; static bottom images content-addressed per image.
- **Gating** — rich template editing stays behind the `custom_branding`
  entitlement (`billing.entitlements.enforce(merchant, "custom_branding")`).
- **Media** — uploads go through `POST /uploads` → `/media/...` URL strings;
  read them with the existing `_local_media_bytes` (local-media only, no SSRF).
- **Best-effort rendering** — a render/storage failure must never break the pass
  or withhold it; fall back to the numeric/default pass (wrap in try/except like
  `google/hero.py` and the Apple download view already do).

## 9. Quality gates / Definition of done

- Backend: `ruff` + `black` + `mypy` + `pytest` all green (run the whole suite,
  not just wallets — the pass builders are widely imported).
- Frontend: `eslint --max-warnings 0` + `prettier --check` + `vite build` +
  `vitest run` green on `frontend/dashboard`.
- A merchant can pick a template, edit colors + stamp icons / bottom image, see a
  faithful **Apple + Google** preview, save, and the real pass reflects it with
  the bottom visual **on top for Apple / under the QR for Google**.
- Work on `dev`; promote to `prod` (`git merge --no-ff`) only when green and the
  user approves. Ship both platforms together.

## 10. Out of scope (do not build)

- User-authored/custom templates (positions are locked by design — code-defined
  only).
- Full offline / queueing.
- Changing the existing freeform editor's behavior (it stays as `custom`).
- Any `core` schema change or tiered-cards work.
