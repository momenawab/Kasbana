import {
  ArrowRightLeft,
  CalendarCheck,
  CalendarClock,
  CheckCircle2,
  FileText,
  Flag,
  Globe,
  Mail,
  MessageCircle,
  PhoneCall,
  StickyNote,
  Trophy,
  UserPlus,
  XCircle,
} from 'lucide-react'
import { fromNow } from '../../lib/format'

// Icon per activity kind. The backend's ActivityKind is the source of truth for
// which of these exist; anything unmapped falls back to a neutral dot rather
// than crashing, so a release that adds a kind degrades quietly.
const ICONS = {
  lead_created: UserPlus,
  website_form_submitted: Globe,
  manual_lead_created: UserPlus,
  phone_call_logged: PhoneCall,
  whatsapp_sent: MessageCircle,
  email_sent: Mail,
  priority_changed: Flag,
  status_changed: ArrowRightLeft,
  assigned_sales_changed: ArrowRightLeft,
  demo_scheduled: CalendarClock,
  demo_completed: CalendarCheck,
  proposal_sent: FileText,
  converted_to_merchant: Trophy,
  closed: XCircle,
  note_added: StickyNote,
}

const TONES = {
  converted_to_merchant: 'text-success',
  demo_scheduled: 'text-warn',
  demo_completed: 'text-warn',
  proposal_sent: 'text-warn',
  closed: 'text-tx-3',
  website_form_submitted: 'text-info',
}

export default function LeadTimeline({ activities = [] }) {
  if (activities.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center">
        <CheckCircle2 size={22} className="mx-auto mb-2 text-tx-3" />
        <div className="text-sm text-tx-2">Nothing has happened yet.</div>
        <div className="mt-1 text-xs text-tx-3">
          Every change to this lead lands here automatically.
        </div>
      </div>
    )
  }

  return (
    <ol className="flex flex-col">
      {activities.map((a, i) => {
        const Icon = ICONS[a.kind] ?? CheckCircle2
        const last = i === activities.length - 1

        return (
          <li key={a.id} className="flex gap-3">
            {/* The rail: an icon per entry with a line joining them, cut short
                on the last so the timeline ends rather than trailing off. */}
            <div className="flex flex-col items-center">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2">
                <Icon size={13} className={TONES[a.kind] ?? 'text-tx-2'} />
              </div>
              {!last && <div className="w-px flex-1 bg-line" />}
            </div>

            <div className={`flex-1 ${last ? 'pb-0' : 'pb-5'}`}>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-medium text-tx">{a.title}</span>
                <span className="text-xs text-tx-3" title={new Date(a.created_at).toLocaleString()}>
                  {fromNow(a.created_at)}
                </span>
              </div>
              {a.description && (
                <div className="mt-0.5 text-sm text-tx-2">{a.description}</div>
              )}
              <div className="mt-0.5 text-xs text-tx-3">{a.actor_label || 'System'}</div>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
