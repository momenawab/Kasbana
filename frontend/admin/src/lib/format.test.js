import { describe, it, expect } from 'vitest'
import { fromNow, shortDate, num, statusTone } from './format.js'

describe('num', () => {
  it('renders an em dash for nullish input', () => {
    expect(num(null)).toBe('—')
    expect(num(undefined)).toBe('—')
  })

  it('thousands-separates numbers', () => {
    expect(num(1234567)).toBe('1,234,567')
  })

  it('formats zero as "0", not a dash', () => {
    expect(num(0)).toBe('0')
  })
})

describe('shortDate / fromNow', () => {
  it('render an em dash for empty values', () => {
    expect(shortDate(null)).toBe('—')
    expect(fromNow('')).toBe('—')
  })

  it('formats a real date', () => {
    expect(shortDate('2026-03-14')).toBe('14 Mar 2026')
  })
})

describe('statusTone', () => {
  it('maps healthy statuses to success', () => {
    expect(statusTone('active')).toBe('success')
    expect(statusTone('PAID')).toBe('success')
  })

  it('maps trial statuses to info', () => {
    expect(statusTone('trialing')).toBe('info')
  })

  it('maps at-risk statuses to warn', () => {
    expect(statusTone('past_due')).toBe('warn')
    expect(statusTone('suspended')).toBe('warn')
  })

  it('maps terminal statuses to danger', () => {
    expect(statusTone('canceled')).toBe('danger')
    expect(statusTone('failed')).toBe('danger')
  })

  it('falls back to neutral for unknown statuses', () => {
    expect(statusTone('whatever')).toBe('neutral')
    expect(statusTone(null)).toBe('neutral')
  })
})
