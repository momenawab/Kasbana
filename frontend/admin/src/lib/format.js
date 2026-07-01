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

// Map a billing/merchant/invoice status string to a Badge tone.
export function statusTone(status) {
  const s = (status || '').toLowerCase()
  if (s === 'active' || s === 'paid') return 'success'
  if (s === 'trial' || s === 'trialing') return 'info'
  if (s === 'past_due' || s === 'suspended' || s === 'pending') return 'warn'
  if (s === 'locked' || s === 'canceled' || s === 'failed') return 'danger'
  return 'neutral'
}
