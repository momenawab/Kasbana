// MSW handlers (Phase 1 starter: auth + /me so the shell boots on a trial).
// Phase 0 expands this to every §6 path with realistic data.
import { http, HttpResponse } from 'msw'
import { db } from './db'

const BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1'

export const handlers = [
  http.post(`${BASE}/auth/token`, () =>
    HttpResponse.json({ access: 'mock-access', refresh: 'mock-refresh' })
  ),
  http.post(`${BASE}/auth/refresh`, () => HttpResponse.json({ access: 'mock-access' })),
  http.get(`${BASE}/me`, () =>
    HttpResponse.json({
      merchant: db.merchant,
      entitlements: db.entitlements,
      staff: db.staff,
    })
  ),
  // Shell renders <AnnouncementBanner> on every authenticated page; it expects an
  // array and does `.filter`, so an unmocked (bypassed) response crashes the app.
  http.get(`${BASE}/announcements`, () => HttpResponse.json([])),
  // Locations table (paginated shape: { results }).
  http.get(`${BASE}/locations`, () => HttpResponse.json({ results: [] })),
]
