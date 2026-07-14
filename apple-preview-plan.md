# Apple-faithful card preview — plan

> **Goal.** Make the pass preview on the dashboard look like a *real* Apple Wallet
> `storeCard`, not an approximation of one. Primarily the **Cards page** tiles
> (`features/cards/CardsList.jsx`), but the same component backs the Card Designer
> and the enroll page, so the work lands in one place:
> `frontend/dashboard/src/components/WalletPreview.jsx`.
>
> **Status: not started.** Spec only. Written 2026-07-14 on `dev`.
>
> Ground rules from [`finalize-plan.md`](./finalize-plan.md) apply: `core` is
> frozen, blank = default, best-effort rendering, and the full gate (backend
> ruff/black/mypy/pytest, frontend eslint/prettier/vitest/build) must be green.

---

## The one thing that has to be decided first

**There is no ground truth to copy.** Apple Wallet is **off in prod** — no Apple
Developer cert, `apple_pass_url` is null, and the enroll page only shows the Google
button. **Nobody has ever seen a real Kasbana Apple pass.** So "make it exactly like
the real card" currently has no referent, and I would be matching Apple's *documented*
`storeCard` layout from memory rather than a real artifact.

**So: what I need from you is one screenshot.** See
[What I need from you](#what-i-need-from-you) at the bottom. Everything else in this
document I can derive from the code, and already have.

---

## What the real pass actually contains (derived — no input needed)

Dumped from `wallets/apple/passdata.py::build_pass_json` for an 8-stamp card, 3 earned:

```
logoText        Kasbana Coffee            top-left, beside the logo image
headerFields    [{key: brand, value: "Stampn"}]     top-right
primaryFields   []                        EMPTY — the strip carries the stamp count
secondaryFields [{label: "8 FOR A REWARD", value: 5}]
auxiliaryFields [{label: "REWARD", value: "Free latte"}]
backFields      Your reward · How it works · Merchant · Powered by Stampn (+ contact/social)
strip           1125×369 PNG — the stamp grid (wallets/stamp_grid.py)
barcode         PKBarcodeFormatQR, altText "C8U9QS" (wallets/shortcode.py)
colors          bg rgb(14,27,42) · fg rgb(255,255,255) · label rgb(255,255,255)
```

The **data** side of the preview is already correct — it renders these fields from
the same template registry the backend uses. The problem is purely **chrome**: how it
is laid out, proportioned and styled.

---

## The fidelity gaps (each one is a concrete diff)

Current Apple branch is `WalletPreview.jsx:312-448`.

### 1. The strip is inset — it must be full-bleed  ← the big one

`WalletPreview.jsx:378-400` renders the strip as `mt-3 rounded-lg p-3` — a rounded,
padded panel *inside* the card. On a real pass the strip image is **full-bleed**: it
spans the entire card width, edge to edge, with **no margin, no padding and no corner
radius**, butted directly under the header row. Today it reads as a card-within-a-card,
which is the single thing that most makes the preview look "not Apple".

### 2. The strip's aspect ratio is not enforced

The backend renders the strip at **1125×369 (≈3.05:1)**. The preview's strip is
whatever height the JS stamp grid happens to take. So the merchant is previewing a
different shape than the pass will show. The preview strip must be locked to 3.05:1.

### 3. The QR is fake

`Barcode` (`WalletPreview.jsx:111-126`) draws a deterministic 5×5 checkerboard — it is
not a QR code. A real pass shows a real QR on a white rounded panel with the short
alt-text beneath it. If the tile is meant to look real, this has to be a real QR (or,
on the Cards page where there is no customer yet, an honest placeholder — see the open
question below).

### 4. Secondary + auxiliary are laid out wrong

`WalletPreview.jsx:420-440` puts secondary and auxiliary in **one** row split by
`justify-between`. On a real pass they are **two separate rows**, each laid out
left-to-right, secondary above auxiliary.

### 5. Primary fields sit below the strip instead of on it

`WalletPreview.jsx:402-417` renders primary *after* the strip. Apple **overlays**
primary fields on top of the strip image. This does not bite today (both stamp
templates set `primary: []`), but it is wrong for any template that uses both.

### 6. Card geometry

Corner radius, width, type scale and the bottom barcode block are all approximations.
This is exactly what the reference screenshot settles.

---

## The architectural decision worth making

The preview draws its stamps **in JavaScript** (`stampRows` + `StampGrid`), mirroring
`wallets/stamp_grid.py::_centers`. Two implementations of one layout — I added tests on
both sides to catch drift, but the drift risk is permanent.

**Option A — keep drawing in JS.** No backend work. Fast, offline, no requests. But the
strip in the preview is forever a *lookalike* of the strip on the pass, and the two can
diverge (fonts, anti-aliasing, custom uploaded stamp icons, the exact band background).

**Option B — serve the real strip PNG.** Add `GET /cards/{id}/strip-preview?count=N`
returning the **actual** `render_stamp_grid` output the pass uses. The preview strip
then *is* the pass strip, pixel for pixel, by construction — including custom uploaded
stamp icons, which JS can only approximate. Cost: one image request per card tile on the
Cards page (content-addressable and cacheable, same as the Google hero), and the tile
depends on the network.

**Recommendation: B, for the Cards page and the Designer.** The whole point of this task
is "the preview should be the real card". Option A guarantees it can never quite be.
B also lets us delete the duplicated JS grid logic. Worth confirming before I build.

---

## Build phases

**P1 — Chrome rebuild (no backend).** Full-bleed strip locked to 3.05:1; secondary and
auxiliary as two rows; primary overlaid on the strip; real Apple radius/type/spacing per
the reference; real QR + alt-text block at the bottom. All in `WalletPreview.jsx`.

**P2 — Real strip (only if Option B).** New `GET /cards/{id}/strip-preview?count=N`
(`dashboard/views.py`, `CanManageCards`, tenancy-scoped, best-effort `try/except` like
`CardQRView`); preview consumes it; delete the JS `stampRows`/`StampGrid` duplication
and the mirroring tests that exist only to guard it.

**P3 — Cards page.** Drop the `zoom: 0.8` hack (`CardsList.jsx:84`) for a proper scale,
so the tile is a faithful miniature rather than a squashed one.

**Tests.** Frontend: the preview renders the strip full-bleed at the right ratio;
secondary/auxiliary land on separate rows; a template with primary fields overlays them.
Backend (P2 only): the endpoint is tenancy-scoped, gated, and returns the same bytes as
the pass strip.

---

## Definition of done

Put the preview tile next to a screenshot of the real pass and they are the same card —
same proportions, same strip, same field placement, same barcode block. Full gate green.

---

## What I need from you

1. **A screenshot of a real Apple Wallet store card, front, full resolution.** This is
   the only real blocker. Ours would be ideal but needs the Apple cert we don't have —
   so **any** real loyalty/store card from your iPhone's Wallet works. I need it to see
   Apple's actual chrome: corner radius, type scale, field spacing, exactly how the strip
   meets the card edges, and the barcode block.
2. **Scope** — Cards page tiles only, or the Card Designer and enroll-page previews too?
   (Same component, so "all" is barely more work.)
3. **Front only, or front + back?** The back exists in the pass (`backFields`) and is not
   previewed at all today.

### Two open questions I can't answer for you

- **The Cards page has no customer.** A card tile shows a *program*, not a specific
  customer's pass — so there is no real QR and no real stamp count (it currently hardcodes
  `stampCount={0}`, `CardsList.jsx:94`). Do you want the tile to show a realistic dummy
  state (e.g. a QR placeholder and a part-filled card), or stay honestly empty?
- **Option A vs B above** — lookalike strip, or the real one.
