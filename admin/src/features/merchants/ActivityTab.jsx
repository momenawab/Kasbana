import { Loader2, Activity, Stamp, Gift, UserPlus, Receipt, Shield, SlidersHorizontal } from 'lucide-react'
import { useActivity } from './api'
import { fromNow } from '../../lib/format'

// Map an event type to an icon. Types come from the backend timeline:
// enroll/stamp/redeem/adjust · invoice_<status> · admin_action.
function iconFor(type) {
  if (type === 'stamp') return Stamp
  if (type === 'redeem') return Gift
  if (type === 'enroll') return UserPlus
  if (type === 'adjust') return SlidersHorizontal
  if (type.startsWith('invoice')) return Receipt
  if (type === 'admin_action') return Shield
  return Activity
}

export default function ActivityTab({ merchantId }) {
  const { data, isLoading } = useActivity(merchantId)
  const events = data ?? []

  if (isLoading) {
    return <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
  }
  if (events.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center text-sm text-tx-3">
        <Activity size={22} className="mx-auto mb-2" />
        No recent activity for this merchant.
      </div>
    )
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <ul className="flex flex-col">
        {events.map((e, i) => {
          const Icon = iconFor(e.type)
          return (
            <li key={i} className="flex items-start gap-3 border-b border-line/60 py-3 last:border-0">
              <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-tx-3">
                <Icon size={14} />
              </span>
              <div className="flex-1">
                <p className="text-sm text-tx-2">{e.summary}</p>
                {(e.meta?.reason || e.meta?.staff || e.meta?.location) && (
                  <p className="text-xs text-tx-3">
                    {[e.meta.reason, e.meta.staff, e.meta.location].filter(Boolean).join(' · ')}
                  </p>
                )}
              </div>
              <span className="whitespace-nowrap text-xs text-tx-3">{fromNow(e.at)}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
