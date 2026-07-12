import { describe, expect, it } from 'vitest'
import { isDarkColor, isLightColor } from './color'

describe('isLightColor', () => {
  it('reads pale fills as light and deep ones as dark', () => {
    expect(isLightColor('#FFFFFF')).toBe(true)
    expect(isLightColor('#E0A23B')).toBe(true) // brand amber
    expect(isLightColor('#000000')).toBe(false)
    expect(isLightColor('#0E1B2A')).toBe(false) // brand navy
  })

  it('accepts 3-digit shorthand and a missing #', () => {
    expect(isLightColor('fff')).toBe(true)
    expect(isLightColor('FFFFFF')).toBe(true)
    expect(isLightColor('#000')).toBe(false)
  })

  it('weights green far above blue', () => {
    expect(isLightColor('#33FF33')).toBe(true)
    expect(isLightColor('#3333FF')).toBe(false)
  })

  // Pure green scores 0.587 * 255 = 149.7 — a hair under the 150 cutoff — so it
  // lands on the dark side and an all-green enroll card gets light text. Pinned
  // because it looks like a bug until you do the arithmetic; if the threshold
  // ever moves, this is the case that should make you think.
  it('treats pure green as (just) dark', () => {
    expect(isLightColor('#00FF00')).toBe(false)
  })
})

describe('isDarkColor', () => {
  it('is true only for a parseable, genuinely dark colour', () => {
    expect(isDarkColor('#0E1B2A')).toBe(true)
    expect(isDarkColor('#2b1a4d')).toBe(true)
    expect(isDarkColor('#FFFFFF')).toBe(false)
  })

  // The enroll card's default surface is light, so anything we cannot parse must
  // fall back to "not dark". Guessing dark would flip the copy to white on a pale
  // background and white it out — the exact bug this helper exists to prevent.
  it('is false for input it cannot parse, not merely "not light"', () => {
    expect(isDarkColor(undefined)).toBe(false)
    expect(isDarkColor('')).toBe(false)
    expect(isDarkColor('linear-gradient(#fff, #eee)')).toBe(false)
    expect(isDarkColor('rgb(0,0,0)')).toBe(false)
    expect(isDarkColor('#12345')).toBe(false)
  })
})
