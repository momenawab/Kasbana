// A drop-in stand-in for `react-i18next` used only by the Wallet Studio
// components copied from the merchant dashboard.
//
// Those files call `useTranslation()`, but the admin console is English-only and
// deliberately carries no i18next dependency — pulling the whole i18n stack into
// a back-office app to resolve ~40 static strings would be a poor trade. This
// shim exposes the same `{ t, i18n }` surface, backed by the exact strings
// lifted from `dashboard/src/locales/en.json` (see `locales/walletStudio.json`),
// so the copied components run unmodified apart from their import path.
//
// Keeping the same call signature is the point: it is what lets those files stay
// textually close to their originals, so a future diff against the dashboard
// shows real drift rather than a wall of mechanical edits.
import strings from '../locales/walletStudio.json'

// Resolve "walletDesign.stripBg" against the nested JSON.
function lookup(key) {
  return key.split('.').reduce((node, part) => (node == null ? undefined : node[part]), strings)
}

// i18next's `{{name}}` interpolation — the only formatting feature these strings
// use (e.g. walletDesign.warnCount's "{{max}}").
function interpolate(template, vars) {
  if (!vars || typeof template !== 'string') return template
  return template.replace(/\{\{(\w+)\}\}/g, (whole, name) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : whole
  )
}

/**
 * `t(key)`, `t(key, fallback)` or `t(key, { ...vars })` — mirrors the subset of
 * the i18next signature the copied components actually use. An unknown key falls
 * back to the supplied default, then to the key itself, which is what i18next
 * does and keeps a missing string visible instead of blank.
 */
export function t(key, second, third) {
  const fallback = typeof second === 'string' ? second : undefined
  const vars = typeof second === 'object' && second !== null ? second : third
  const value = lookup(key)
  if (typeof value === 'string') return interpolate(value, vars)
  return fallback ?? key
}

export function useTranslation() {
  // `language` drives arDigits() in WalletPreview; the console is English-only,
  // so the previews render Western digits — matching what an admin authoring a
  // pass expects to read back.
  return { t, i18n: { language: 'en' } }
}
