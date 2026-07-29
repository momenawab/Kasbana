// Pass geometry — the coordinate spaces the wallet passes are actually drawn in,
// and the stamp grid computed inside them.
//
// Split out of WalletPreview.jsx rather than living beside the component: these
// are constants and a pure function, and a file that exports both components and
// non-components breaks React Fast Refresh (react-refresh/only-export-components).
// The preview, the design editor and the tests all read them from here.

// The canvases the backend actually renders into (wallets/apple/signing.py and
// wallets/google/hero.py). Drawing the preview in these same coordinate spaces is
// what locks its proportions to the pass's instead of to whatever the DOM does.
export const APPLE_STRIP = [1125, 369]
export const GOOGLE_HERO = [1032, 336]

// ── Stamp geometry ────────────────────────────────────────────────────────────
// A direct port of wallets/stamp_grid.py::_centers, working in the same pixel
// space the backend draws into. Same padding, same pitch, same radius formula —
// so the preview's stamps are the pass's stamps in shape AND in scale, not just
// in arrangement. (The old preview drew fixed 20px glyphs, which on a 3-stamp
// card came out roughly half the size the pass renders them.)
// Mirrors STAMP_FILL / ICON_W_FILL / ICON_H_FILL in wallets/stamp_grid.py.
// Diameter is 2 × STAMP_FILL, so anything below 0.5 guarantees a gap between
// neighbours.
export const STAMP_FILL = 0.44
// Uploaded icons are fitted to a BOX and keep their own aspect ratio, rather
// than being squashed into a square sized by the tighter axis. On a strip far
// wider than it is tall that axis was always the pitch, so artwork covered ~44%
// of the band height and the rest sat empty.
export const ICON_W_FILL = 0.94
export const ICON_H_FILL = 0.92

// Vertical padding by row count — the port of _pad_y_factor. A single row sits
// in the middle of the strip with nothing above or below it, so generous
// padding is only wasted height; two rows genuinely need the space or they
// crowd. Since the vertical axis binds for every card except 4 and 5 stamps,
// this is what actually decides how big a stamp looks.
function padYFactor(rows) {
  return rows === 1 ? 0.06 : 0.09
}

export function stampGeometry(count, layout, size = APPLE_STRIP) {
  const [w, h] = size
  const n = Math.max(1, Math.min(count, 15)) // cap so a big card doesn't render dust
  const rows = n <= 5 ? 1 : 2
  const cols = Math.ceil(n / rows)
  const padX = Math.trunc(w * 0.04)
  const padY = Math.trunc(h * padYFactor(rows))
  const cellW = (w - 2 * padX) / cols
  const cellH = (h - 2 * padY) / rows

  let centers
  let pitch
  if ((layout === 'columns' || layout === 'stagger') && rows > 1) {
    // Both alternate down the rows — stamp i sits on row `i % rows`, column
    // `i // rows` — so a 6-stamp card runs 0,2,4 across the top and 1,3,5 across
    // the bottom. STAGGER additionally slides each lower row half a column along,
    // which is what turns the grid into a zigzag.
    const units = []
    for (let i = 0; i < n; i++) {
      const r = i % rows
      const c = Math.floor(i / rows)
      units.push([r, c + 0.5 + (layout === 'stagger' ? 0.5 * r : 0)])
    }
    const lo = Math.min(...units.map(([, u]) => u))
    const hi = Math.max(...units.map(([, u]) => u))
    // +1.0 leaves half a pitch of margin either side, so the row that sticks out
    // furthest (the staggered one) still sits inside the padding.
    pitch = (w - 2 * padX) / (hi - lo + 1)
    centers = units.map(([r, u], i) => ({
      i,
      row: r,
      x: padX + (u - lo + 0.5) * pitch,
      y: padY + r * cellH + cellH / 2,
    }))
  } else {
    pitch = cellW
    centers = []
    for (let i = 0; i < n; i++) {
      const row = Math.floor(i / cols)
      const c = i % cols
      // centre the last row if it is short
      const inRow = row < rows - 1 ? cols : n - cols * (rows - 1)
      const rowW = inRow * cellW
      centers.push({
        i,
        row,
        x: (w - rowW) / 2 + c * cellW + cellW / 2,
        y: padY + row * cellH + cellH / 2,
      })
    }
  }

  // A circle stays bound by the tighter axis (it is round — using the taller
  // axis would just overlap its neighbours). An icon gets the full box and keeps
  // its own aspect ratio, fitted at draw time.
  const radius = Math.trunc(Math.min(pitch, cellH) * STAMP_FILL)
  return {
    centers,
    pitch,
    radius,
    ring: Math.max(4, Math.trunc(radius / 7)),
    iconW: Math.trunc(pitch * ICON_W_FILL),
    iconH: Math.trunc(cellH * ICON_H_FILL),
  }
}
