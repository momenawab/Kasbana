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

// Map a billing/merchant status string to a Badge tone.
export function statusTone(status) {
  const s = (status || '').toLowerCase()
  if (s === 'active') return 'success'
  if (s === 'trial' || s === 'trialing') return 'info'
  if (s === 'past_due' || s === 'suspended') return 'warn'
  if (s === 'locked' || s === 'canceled') return 'danger'
  return 'neutral'
}
