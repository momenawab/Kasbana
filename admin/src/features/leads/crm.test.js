import { describe, it, expect } from 'vitest'
import { colorFor, labelFor, optionsFor, scoreTone, slugify, titleCase } from './crm'

// The choice rows as GET /crm/choices returns them, grouped the way useCrmChoices
// hands them to callers.
const CHOICES = {
  status: [
    { slug: 'new_lead', label: 'New Lead', color: '#3b82f6' },
    { slug: 'hot_lead', label: 'Chase Now', color: '' },
  ],
  category: [{ slug: 'cafe', label: 'Café', color: '' }],
}

describe('labelFor', () => {
  it('uses the label an admin configured, not the slug', () => {
    // The whole point of the settings overlay: relabel in Settings, and the
    // console follows without a deploy.
    expect(labelFor(CHOICES, 'status', 'hot_lead')).toBe('Chase Now')
  })

  it('falls back to a readable version of a slug with no choice row', () => {
    // A lead can hold a value whose row was deactivated. History must stay
    // legible rather than render blank.
    expect(labelFor(CHOICES, 'status', 'do_not_call_again')).toBe('Do Not Call Again')
  })

  it('renders an em dash for an empty value', () => {
    expect(labelFor(CHOICES, 'status', '')).toBe('—')
    expect(labelFor(CHOICES, 'status', null)).toBe('—')
  })

  it('does not crash before the choices have loaded', () => {
    expect(labelFor(undefined, 'status', 'new_lead')).toBe('New Lead')
  })
})

describe('colorFor', () => {
  it('returns the configured colour', () => {
    expect(colorFor(CHOICES, 'status', 'new_lead')).toBe('#3b82f6')
  })

  it('returns empty for a value with no colour, so the neutral badge wins', () => {
    expect(colorFor(CHOICES, 'status', 'hot_lead')).toBe('')
    expect(colorFor(CHOICES, 'status', 'unknown')).toBe('')
    expect(colorFor(undefined, 'status', 'new_lead')).toBe('')
  })
})

describe('optionsFor', () => {
  it('returns a kind’s rows', () => {
    expect(optionsFor(CHOICES, 'category')).toHaveLength(1)
  })

  it('returns an empty list for an unknown kind or before load', () => {
    expect(optionsFor(CHOICES, 'nope')).toEqual([])
    expect(optionsFor(undefined, 'status')).toEqual([])
  })
})

describe('titleCase', () => {
  it('turns a slug into words', () => {
    expect(titleCase('demo_scheduled')).toBe('Demo Scheduled')
  })

  it('handles empty input', () => {
    expect(titleCase('')).toBe('')
    expect(titleCase()).toBe('')
  })
})

describe('slugify', () => {
  // The slug is what every lead stores and the server refuses to re-slug a row
  // afterwards, so a bad slug here is permanent. These pin the shape.
  it('matches the shape of the built-in slugs', () => {
    expect(slugify('Do Not Call Again')).toBe('do_not_call_again')
    expect(slugify('Walk-In')).toBe('walk_in')
  })

  it('keeps accented words whole', () => {
    // "caf" would be a different category from the seeded "cafe", and nobody
    // could tell them apart in the dropdown.
    expect(slugify('Café')).toBe('cafe')
  })

  it('drops punctuation and surrounding whitespace rather than encoding it', () => {
    expect(slugify('  Ghosted!!  ')).toBe('ghosted')
    expect(slugify('Owner / Manager')).toBe('owner_manager')
  })

  it('survives empty and junk input without throwing', () => {
    expect(slugify('')).toBe('')
    expect(slugify()).toBe('')
    expect(slugify('!!!')).toBe('')
  })
})

describe('scoreTone', () => {
  it('greens a strong lead and greys a weak one', () => {
    expect(scoreTone(85).text).toBe('text-success')
    expect(scoreTone(10).text).toBe('text-tx-3')
  })

  it('warns in the middle', () => {
    expect(scoreTone(50).text).toBe('text-warn')
  })

  it('is inclusive at the thresholds', () => {
    expect(scoreTone(70).text).toBe('text-success')
    expect(scoreTone(40).text).toBe('text-warn')
    expect(scoreTone(39).text).toBe('text-tx-3')
  })
})
