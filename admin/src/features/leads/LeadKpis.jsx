import {
  Users,
  Globe,
  UserPlus,
  Heart,
  CalendarCheck,
  Trophy,
  PhoneCall,
  CalendarClock,
  AlarmClock,
  TrendingUp,
} from 'lucide-react'
import { num } from '../../lib/format'

// The cards, in the order a sales lead reads them: how big is the pipeline,
// where did it come from, how is it progressing, what do I do today.
//
// `filter` is what the card puts into the table when clicked — the numbers are
// not decoration, they are the fastest way to the rows behind them. A card
// without one (the two totals, the rate) is a fact, not a slice.
const CARDS = [
  { key: 'total', label: 'Total Leads', Icon: Users },
  { key: 'website', label: 'Website', Icon: Globe, filter: { lead_type: ['website'] } },
  { key: 'manual', label: 'Manual', Icon: UserPlus, filter: { lead_type: ['manual'] } },
  { key: 'interested', label: 'Interested', Icon: Heart, filter: { status: ['interested'] } },
  {
    key: 'demo_scheduled',
    label: 'Demo Scheduled',
    Icon: CalendarCheck,
    filter: { status: ['demo_scheduled'] },
  },
  {
    key: 'customers',
    label: 'Customers',
    Icon: Trophy,
    tone: 'text-success',
    filter: { status: ['customer', 'converted'] },
  },
  { key: 'calls_today', label: "Today's Calls", Icon: PhoneCall },
  {
    key: 'follow_ups_today',
    label: "Today's Follow-ups",
    Icon: CalendarClock,
    tone: 'text-info',
    filter: 'today',
  },
  {
    key: 'overdue_follow_ups',
    label: 'Overdue',
    Icon: AlarmClock,
    // Overdue is the one number that should nag. It only goes red when there is
    // something to nag about — a red 0 trains people to ignore the colour.
    toneWhenNonZero: 'text-danger',
    filter: 'overdue',
  },
  { key: 'conversion_rate', label: 'Conversion', Icon: TrendingUp, suffix: '%' },
]

export default function LeadKpis({ data, isLoading, onDrill }) {
  if (isLoading && !data) return <KpiSkeleton />

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {CARDS.map(({ key, label, Icon, tone, toneWhenNonZero, suffix, filter }) => {
        const value = data?.[key] ?? 0
        const valueTone = (value > 0 && toneWhenNonZero) || tone || 'text-tx'
        const clickable = Boolean(filter) && value > 0

        return (
          <button
            key={key}
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onDrill(filter)}
            className={`rounded-card border border-line bg-surface p-4 text-left transition ${
              clickable
                ? 'cursor-pointer hover:border-brand/60 hover:bg-surface-2'
                : 'cursor-default'
            }`}
          >
            <div className="flex items-center gap-2 text-tx-3">
              <Icon size={15} />
              <span className="truncate text-xs">{label}</span>
            </div>
            <div className={`mt-2 font-num text-2xl ${valueTone}`}>
              {num(value)}
              {suffix && <span className="ml-0.5 text-base text-tx-3">{suffix}</span>}
            </div>
          </button>
        )
      })}
    </div>
  )
}

function KpiSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="rounded-card border border-line bg-surface p-4">
          <div className="h-3 w-20 animate-pulse rounded bg-surface-2" />
          <div className="mt-3 h-7 w-12 animate-pulse rounded bg-surface-2" />
        </div>
      ))}
    </div>
  )
}
