import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

export function fromNow(value) {
  return value ? dayjs(value).fromNow() : '—'
}

export function shortDate(value) {
  return value ? dayjs(value).format('DD MMM YYYY') : '—'
}

export function num(n) {
  return n == null ? '—' : Number(n).toLocaleString('en-US')
}

// Eastern-Arabic digits. Ported from the merchant dashboard's lib/format so the
// Wallet Studio's copied WalletPreview renders identically to the merchant's —
// the console itself is English-only, but the preview must be able to show a
// pass exactly as an Arabic-locale customer will see it.
const AR_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩']

export function arDigits(value, lang) {
  const s = String(value ?? '')
  if (lang !== 'ar') return s
  return s.replace(/[0-9]/g, (d) => AR_DIGITS[Number(d)])
}

// Map a billing/merchant/invoice status string to a Badge tone.
export function statusTone(status) {
  const s = (status || '').toLowerCase()
  if (s === 'active' || s === 'paid') return 'success'
  if (s === 'trial' || s === 'trialing') return 'info'
  if (s === 'past_due' || s === 'suspended' || s === 'pending') return 'warn'
  if (s === 'locked' || s === 'canceled' || s === 'failed') return 'danger'
  return 'neutral'
}
