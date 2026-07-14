// The preview draws its own stamps in JS while the real pass is drawn by Pillow
// on the server. These assertions are the contract between the two: they mirror
// backend/tests/test_stamp_layout.py, so if either side's arrangement drifts, one
// of the two suites fails.
import { describe, expect, it } from 'vitest'

import { stampRows } from './WalletPreview'

describe('stampRows', () => {
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
})
