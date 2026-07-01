// In-memory seed for MSW (Phase 1 starter — Phase 0 expands this to the full §6).
import dayjs from 'dayjs'

export const db = {
  merchant: {
    id: '00000000-0000-0000-0000-000000000001',
    name: 'Cairo Coffee',
    slug: 'cairo-coffee',
    status: 'trial',
    plan: 'trial',
    trial_ends_at: dayjs().add(10, 'day').toISOString(),
    logo_url: null,
    color_bg: '#0E1B2A',
    color_fg: '#FFFFFF',
  },
  // Trial = Growth-level entitlements (mirrors the backend trial rule).
  entitlements: {
    plan: 'trial',
    limits: { max_cards: 10, max_locations: 10, max_staff: 25, max_customers: 20000 },
    features: { whatsapp: true, export: true, api: true, automations: 5, analytics: 'full' },
    usage: { cards: 2, locations: 1, staff: 3, customers: 30, whatsapp_used: 0, whatsapp_quota: null },
  },
  staff: { role: 'OWNER' },
}
