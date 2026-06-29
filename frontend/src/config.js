// ─────────────────────────────────────────────────────────────────────────────
// Site-wide configuration. Edit these in this one place.
// ─────────────────────────────────────────────────────────────────────────────

// Business contact email (shown on the site + Web3Forms reply-to).
export const CONTACT_EMAIL = 'contact@kasbana.net'

// Canonical domain, used for Open Graph / canonical tags.
export const SITE_URL = 'https://kasbana.net'

// Client Dashboard (separate app on its own subdomain). The marketing CTAs link
// here. Override in dev with VITE_DASHBOARD_URL=http://localhost:5174.
export const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'https://app.kasbana.net'
export const DASHBOARD_LOGIN_URL = `${DASHBOARD_URL}/login`
export const DASHBOARD_SIGNUP_URL = `${DASHBOARD_URL}/signup`

// Brand
export const BRAND_NAME = 'Kasbana'
export const BRAND_NAME_AR = 'كسبانة'
export const ONE_LINER =
  "Digital loyalty cards that live in your customers' phone wallet — no app needed."
export const ONE_LINER_AR =
  'كروت ولاء رقمية في محفظة عملائك — من غير أي تطبيق.'
