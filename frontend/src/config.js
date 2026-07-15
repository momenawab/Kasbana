// ─────────────────────────────────────────────────────────────────────────────
// Site-wide configuration. Edit these in this one place.
// ─────────────────────────────────────────────────────────────────────────────

// Business contact email (shown on the site + Web3Forms reply-to).
export const CONTACT_EMAIL = 'contact@stampn.net'

// Business phone + address (shown on the Contact page + footer; required for
// the payment-gateway merchant profile).
export const CONTACT_PHONE = '+201015425157'
export const CONTACT_PHONE_DISPLAY = '+20 101 542 5157'
export const BUSINESS_ADDRESS = 'Cairo, Egypt'
export const BUSINESS_ADDRESS_AR = 'القاهرة، مصر'

// Canonical domain, used for Open Graph / canonical tags.
export const SITE_URL = 'https://stampn.net'

// Client Dashboard (separate app on its own subdomain). The marketing CTAs link
// here. Override in dev with VITE_DASHBOARD_URL=http://localhost:5174.
export const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'https://app.stampn.net'
export const DASHBOARD_LOGIN_URL = `${DASHBOARD_URL}/login`
export const DASHBOARD_SIGNUP_URL = `${DASHBOARD_URL}/signup`

// Backend API (public endpoints only, e.g. the "Get started" lead form).
// Override in dev with VITE_API_URL=http://localhost:8000.
export const API_URL = import.meta.env.VITE_API_URL || 'https://api.stampn.net'
export const LEADS_ENDPOINT = `${API_URL}/api/v1/leads`
export const CONTACT_ENDPOINT = `${API_URL}/api/v1/contact`

// Brand
export const BRAND_NAME = 'Stampn'
export const BRAND_NAME_AR = 'Stampn'
export const ONE_LINER =
  "Digital loyalty cards that live in your customers' phone wallet — no app needed."
export const ONE_LINER_AR =
  'كروت ولاء رقمية في محفظة عملائك — من غير أي تطبيق.'
