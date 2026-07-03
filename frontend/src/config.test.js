import { describe, it, expect } from 'vitest'
import {
  CONTACT_EMAIL,
  SITE_URL,
  DASHBOARD_URL,
  DASHBOARD_LOGIN_URL,
  DASHBOARD_SIGNUP_URL,
} from './config.js'

describe('site config', () => {
  it('exposes the canonical contact email and site URL', () => {
    expect(CONTACT_EMAIL).toBe('contact@stampn.net')
    expect(SITE_URL).toBe('https://stampn.net')
  })

  it('derives dashboard login/signup URLs from the dashboard base', () => {
    expect(DASHBOARD_LOGIN_URL).toBe(`${DASHBOARD_URL}/login`)
    expect(DASHBOARD_SIGNUP_URL).toBe(`${DASHBOARD_URL}/signup`)
  })

  it('uses an absolute https dashboard URL by default', () => {
    expect(DASHBOARD_URL).toMatch(/^https?:\/\//)
  })
})
