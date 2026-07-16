// The preview draws its own stamps in JS while the real pass is drawn by Pillow
// on the server. These assertions are the contract between the two: they mirror
// backend/tests/test_stamp_layout.py, so if either side's arrangement drifts, one
// of the two suites fails. The rest of the file pins the Apple chrome — the things
// that make a preview read as a real storeCard rather than an approximation of one.
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import '../lib/i18n'
import WalletPreview, { APPLE_STRIP, stampGeometry } from './WalletPreview'

// Which stamps land on which row, read back off the geometry the strip is actually
// drawn from — so this guards the real render path, not a lookalike of it.
function stampRows(n, layout) {
  const rows = []
  for (const c of stampGeometry(n, layout).centers) {
    rows[c.row] ||= []
    rows[c.row].push(c.i)
  }
  return rows
}

describe('stamp arrangement', () => {
  it('runs across each row by default', () => {
    expect(stampRows(6, '')).toEqual([
      [0, 1, 2],
      [3, 4, 5],
    ])
  })

  it.each(['columns', 'stagger'])('alternates down the rows for %s', (layout) => {
    // The thing actually asked for: 0,2,4 on top and 1,3,5 below.
    expect(stampRows(6, layout)).toEqual([
      [0, 2, 4],
      [1, 3, 5],
    ])
  })

  it('keeps 5 or fewer stamps on one row, whatever the layout', () => {
    for (const layout of ['', 'columns', 'stagger']) {
      expect(stampRows(5, layout)).toEqual([[0, 1, 2, 3, 4]])
    }
  })

  it('falls back to the default row layout on an unknown value', () => {
    expect(stampRows(6, 'nonsense')).toEqual(stampRows(6, ''))
  })

  it('handles an odd count — the top row takes the extra stamp', () => {
    expect(stampRows(7, 'columns')).toEqual([
      [0, 2, 4, 6],
      [1, 3, 5],
    ])
  })

  it('offsets the lower row only for stagger — that is the whole zigzag', () => {
    const rowX = (layout, row) => stampGeometry(6, layout).centers.filter((c) => c.row === row)[0].x
    expect(rowX('columns', 1)).toBeCloseTo(rowX('columns', 0), 5)
    expect(rowX('stagger', 1)).toBeGreaterThan(rowX('stagger', 0))
  })
})

describe('stampGeometry', () => {
  // Worked through by hand from wallets/stamp_grid.py::render_stamp_grid on the
  // real 1125×369 strip: pad 67/51, cell 330.33×267, so radius = int(267 * 0.34).
  // Not just the arrangement — the *scale*. The preview used to draw every stamp at
  // a flat 20px, which on a 3-stamp card is less than half what the pass renders.
  it('sizes stamps the way the backend does, not at a fixed size', () => {
    const { radius, ring, iconSize } = stampGeometry(3, 'grid', APPLE_STRIP)
    expect(radius).toBe(90)
    expect(ring).toBe(12)
    expect(iconSize).toBe(218)
  })

  it('spreads the stamps across the full strip width', () => {
    const { centers } = stampGeometry(3, 'grid', APPLE_STRIP)
    const [w] = APPLE_STRIP
    // Symmetric about the centreline, and reaching out toward the padding.
    expect(centers[1].x).toBeCloseTo(w / 2, 0)
    expect(centers[0].x).toBeLessThan(w * 0.25)
    expect(centers[2].x).toBeGreaterThan(w * 0.75)
  })

  it('shrinks the stamps when an alternating layout packs in more columns', () => {
    // columns/stagger fit ceil(n/2) columns where grid fits the same count across
    // two rows — the pitch tightens, so the glyphs have to come down with it.
    const grid = stampGeometry(10, 'grid', APPLE_STRIP)
    const stagger = stampGeometry(10, 'stagger', APPLE_STRIP)
    expect(stagger.pitch).toBeLessThan(grid.pitch)
    expect(stagger.radius).toBeLessThanOrEqual(grid.radius)
  })
})

// A stamp template: bottom visual is the strip, and it carries a primary field —
// which is what lets us prove primary is overlaid ON the strip rather than under it.
const STAMP_TEMPLATE = {
  key: 'coffee',
  bottom_visual: 'stamps',
  apple: {
    header: [],
    primary: [{ label: 'Balance', source: 'balance' }],
    secondary: [{ label: '{goal} for a reward', source: 'stamps' }],
    auxiliary: [{ label: 'Reward', source: 'reward' }],
  },
}

function renderApple(props = {}) {
  return render(
    <WalletPreview
      platform="APPLE"
      merchantName="Kasbana Coffee"
      rewardTitle="Free latte"
      stampsRequired={8}
      stampCount={3}
      shortCode="C8U9QS"
      {...props}
    />
  )
}

describe('Apple storeCard chrome', () => {
  it('renders the strip full-bleed — no inset, no padding, no corner radius', () => {
    renderApple()
    const strip = screen.getByTestId('apple-strip')
    // Full-bleed means it is a direct child of the card, spanning it edge to edge.
    expect(strip.parentElement).toBe(screen.getByTestId('apple-pass'))
    expect(strip.className).toContain('w-full')
    // The old preview wrapped it in `mt-3 rounded-lg p-3` — a card inside a card.
    expect(strip.className).not.toMatch(/rounded|(^|\s)[pm][xytblr]?-/)
  })

  it('locks the strip to the aspect ratio the pass actually renders', () => {
    renderApple()
    expect(screen.getByTestId('apple-strip').style.aspectRatio).toBe('1125 / 369')
  })

  it('overlays the primary fields on the strip', () => {
    renderApple({ template: STAMP_TEMPLATE })
    const strip = screen.getByTestId('apple-strip')
    expect(strip).toContainElement(screen.getByTestId('apple-primary'))
  })

  it('puts secondary and auxiliary on two separate rows', () => {
    renderApple({ template: STAMP_TEMPLATE })
    const secondary = screen.getByTestId('apple-secondary')
    const auxiliary = screen.getByTestId('apple-auxiliary')
    // One row split by justify-between would nest them in a shared parent row; on a
    // real pass they are siblings, secondary above auxiliary.
    expect(secondary).not.toContainElement(auxiliary)
    expect(auxiliary).not.toContainElement(secondary)
    expect(secondary.compareDocumentPosition(auxiliary)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('draws a real QR, not a checkerboard, with the short code beneath it', () => {
    renderApple()
    const qr = screen.getByTestId('pass-qr')
    expect(qr.tagName.toLowerCase()).toBe('svg')
    // qrcode.react emits path data; the old fake drew 25 flat <span> cells.
    expect(qr.querySelectorAll('path').length).toBeGreaterThan(0)
    expect(screen.getByText('C8U9QS')).toBeInTheDocument()
  })

  it('drops the strip and puts primary back in the flow when the strip is off', () => {
    renderApple({ design: { apple_strip_enabled: false } })
    expect(screen.queryByTestId('apple-strip')).not.toBeInTheDocument()
    expect(screen.getByTestId('apple-primary')).toBeInTheDocument()
  })
})
