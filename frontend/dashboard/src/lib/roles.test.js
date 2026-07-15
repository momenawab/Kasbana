import { describe, it, expect } from 'vitest'
import { canAccess, landingFor, areaForPath } from './roles.js'

describe('canAccess', () => {
  it('lets OWNER/ADMIN reach every area', () => {
    expect(canAccess('OWNER', 'billing')).toBe(true)
    expect(canAccess('ADMIN', 'team')).toBe(true)
  })

  it('restricts SCANNER to the till only', () => {
    expect(canAccess('SCANNER', 'scan')).toBe(true)
    expect(canAccess('SCANNER', 'billing')).toBe(false)
  })

  it('keeps arealess screens open to everyone', () => {
    expect(canAccess('SCANNER', null)).toBe(true)
  })

  it('denies unknown roles', () => {
    expect(canAccess('GHOST', 'scan')).toBe(false)
  })
})

describe('landingFor', () => {
  it('sends a cashier straight to the till', () => {
    expect(landingFor('SCANNER')).toBe('/scan')
  })

  it('sends everyone else to the overview', () => {
    expect(landingFor('OWNER')).toBe('/')
  })
})

describe('areaForPath', () => {
  it('maps the root to insights', () => {
    expect(areaForPath('/')).toBe('insights')
  })

  it('maps nested paths by prefix', () => {
    expect(areaForPath('/campaigns/new')).toBe('engage')
    expect(areaForPath('/billing')).toBe('billing')
  })

  it('returns null for open screens', () => {
    expect(areaForPath('/settings')).toBeNull()
  })
})
