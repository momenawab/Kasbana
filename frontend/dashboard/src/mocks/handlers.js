// MSW handlers (Phase 1 starter: auth + /me so the shell boots on a trial).
// Phase 0 expands this to every §6 path with realistic data.
import { http, HttpResponse } from 'msw'
import { db } from './db'

const BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1'

// Analytics fixtures. The real endpoint returns one gap-filled bucket per day, so
// mirror that: a deterministic weekday-shaped curve (weekends run hot for a coffee
// shop) rather than noise, so the charts and the expanded per-day view look real.
const METRIC_BASE = { joins: 4, stamps: 22, redemptions: 3 }

function seriesPoints(metric, from, to) {
  const end = from && to ? new Date(`${to}T00:00:00`) : new Date()
  const start =
    from && to ? new Date(`${from}T00:00:00`) : new Date(end.getTime() - 29 * 86400000)
  const base = METRIC_BASE[metric] ?? 5

  const points = []
  for (let d = new Date(start); d <= end; d = new Date(d.getTime() + 86400000)) {
    const dow = d.getDay()
    const weekend = dow === 5 || dow === 6 ? 1.9 : 1
    // Deterministic wobble keyed on the date, so a reload shows the same chart.
    const wobble = ((d.getDate() * 7919) % 11) / 10
    const value = Math.max(0, Math.round(base * weekend * (0.55 + wobble * 0.6)))
    points.push({ date: d.toISOString().slice(0, 10), value })
  }
  return points
}

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
  // Analytics (§14) — summary KPIs + the per-metric day buckets the charts plot.
  http.get(`${BASE}/analytics/summary`, () =>
    HttpResponse.json({
      enrollments: 1284,
      active_cards: 412,
      redemptions: 96,
      repeat_rate: 0.38,
      apple_count: 268,
      google_count: 144,
    })
  ),
  http.get(`${BASE}/analytics/timeseries`, ({ request }) => {
    const url = new URL(request.url)
    const metric = url.searchParams.get('metric') ?? 'joins'
    return HttpResponse.json({
      points: seriesPoints(metric, url.searchParams.get('from'), url.searchParams.get('to')),
    })
  }),
  // Wallet split — the same two counts /summary carries, but scoped to the date
  // range. Derive them from the window so narrowing the dates visibly moves the
  // donut, the way the real endpoint does.
  http.get(`${BASE}/analytics/wallet_split`, ({ request }) => {
    const url = new URL(request.url)
    const joins = seriesPoints('joins', url.searchParams.get('from'), url.searchParams.get('to'))
    const total = joins.reduce((sum, p) => sum + p.value, 0)
    return HttpResponse.json({
      apple_count: Math.round(total * 0.65),
      google_count: total - Math.round(total * 0.65),
    })
  }),
  // Business settings (§14) — GET seeds the form; PATCH merges & echoes back so a
  // save in the Business tab persists for the rest of the session.
  http.get(`${BASE}/settings/business`, () => HttpResponse.json(db.businessSettings)),
  http.patch(`${BASE}/settings/business`, async ({ request }) => {
    const body = await request.json()
    const { contact, ...rest } = body
    Object.assign(db.businessSettings, rest, contact?.phone ? { phone: contact.phone } : {})
    return HttpResponse.json(db.businessSettings)
  }),
  // Registration-page (enroll) theme — GET seeds the editor; PATCH merges &
  // echoes so a save in the "Registration page" tab persists for the session.
  http.get(`${BASE}/settings/enroll-theme`, () => HttpResponse.json(db.enrollTheme)),
  http.patch(`${BASE}/settings/enroll-theme`, async ({ request }) => {
    Object.assign(db.enrollTheme, await request.json())
    return HttpResponse.json(db.enrollTheme)
  }),
  // Account settings (§14) — the Account tab stays blank until this GET resolves.
  http.get(`${BASE}/settings/account`, () => HttpResponse.json(db.accountSettings)),
  http.patch(`${BASE}/settings/account`, async ({ request }) => {
    Object.assign(db.accountSettings, await request.json())
    return HttpResponse.json(db.accountSettings)
  }),
]
