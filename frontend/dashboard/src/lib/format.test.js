import { describe, it, expect } from 'vitest'
import { arDigits, money, daysUntil } from './format.js'

describe('arDigits', () => {
  it('leaves Western digits untouched for non-Arabic', () => {
    expect(arDigits(199, 'en')).toBe('199')
  })

  it('maps Western digits to Arabic-Indic for Arabic', () => {
    expect(arDigits('199', 'ar')).toBe('١٩٩')
  })

  it('handles null/undefined as empty string', () => {
    expect(arDigits(null, 'ar')).toBe('')
    expect(arDigits(undefined, 'en')).toBe('')
  })
})

describe('money', () => {
  it('formats EGP major units in English', () => {
    expect(money(1999, 'en')).toBe('EGP 1,999')
  })

  it('formats with Arabic digits and suffix', () => {
    expect(money(199, 'ar')).toBe('١٩٩ ج.م')
  })

  it('defaults a nullish amount to zero', () => {
    expect(money(null, 'en')).toBe('EGP 0')
  })
})

describe('daysUntil', () => {
  it('never returns negative for a past date', () => {
    expect(daysUntil('2000-01-01')).toBe(0)
  })

  it('returns a positive count for a future date', () => {
    const future = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString()
    expect(daysUntil(future)).toBeGreaterThanOrEqual(4)
  })
})
