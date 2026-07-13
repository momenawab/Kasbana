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
    features: { export: true, api: true, automations: 5, analytics: 'full' },
    usage: { cards: 2, locations: 1, staff: 3, customers: 30 },
  },
  staff: { role: 'OWNER' },
  // Business settings (§14). Mutable so a mocked PATCH persists in-session and the
  // form reflects saves. Seeded to match the merchant brand above.
  businessSettings: {
    name: 'Cairo Coffee',
    legal_name: 'Cairo Coffee LLC',
    logo_url: null,
    address: '12 Nile St, Cairo',
    color_bg: '#0E1B2A',
    color_fg: '#FFFFFF',
    enroll_headline: '',
    enroll_tagline: '',
    phone: '+20 100 000 0000',
    facebook_url: '',
    instagram_url: '',
    whatsapp: '',
    tiktok_url: '',
    terms_url: '',
    branches: '',
  },
  // Registration-page (enroll) theme (§ finalize Phase 2). Mutable so a mocked
  // PATCH persists in-session. bg_color left empty so the preview showcases its
  // warm default; name + email fields shown so the mock preview looks populated.
  enrollTheme: {
    template_key: 'classic',
    cover_image_url: '',
    bg_color: '',
    accent_color: '',
    button_text_color: '',
    font: 'system',
    welcome_body: '',
    fields_config: {
      phone: { show: true, required: true },
      name: { show: true, required: true },
      email: { show: true, required: false },
      birthday: { show: false, required: false },
    },
    qr_style: { module_style: 'square', fg_color: '', bg_color: '', frame: 'none' },
    terms_url: '',
    privacy_url: '',
  },
  // Account settings (§14, Account tab). Without this the tab renders blank in
  // mock mode: AccountTab bails with `if (!form) return null` until the GET lands.
  accountSettings: {
    language: 'en',
    notifications: { email: true, whatsapp: false },
  },
}
