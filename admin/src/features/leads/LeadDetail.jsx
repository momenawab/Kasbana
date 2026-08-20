import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Building2,
  Facebook,
  GitMerge,
  Globe,
  Instagram,
  Loader2,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  PhoneCall,
  Trash2,
} from 'lucide-react'
import { useDeleteLead, useLead, useSalesUsers, useUpdateLead } from './api'
import { KIND, labelFor, optionsFor, scoreTone, titleCase, useCrmChoices } from './crm'
import LeadTimeline from './LeadTimeline'
import LogCallModal from './LogCallModal'
import ConvertModal from './ConvertModal'
import MergeModal from './MergeModal'
import LeadLogo from './LeadLogo'
import Badge from '../../components/Badge'
import { fromNow, shortDate } from '../../lib/format'
import { useAuth } from '../../hooks/useAuth'

const CAN_MANAGE = ['SUPER_ADMIN', 'SALES']
// Mirrors the LEADS_CONVERT permission in console/rbac.py. The server is the
// authority — this only decides whether to render a button that would 403.
const CAN_CONVERT = ['SUPER_ADMIN', 'SALES']
const TABS = ['Activity', 'Calls', 'Details']

export default function LeadDetail() {
  const { id } = useParams()
  const { role } = useAuth()
  const canManage = CAN_MANAGE.includes(role)
  const canConvert = CAN_CONVERT.includes(role)

  const { data: lead, isLoading, isError } = useLead(id)
  const { data: choices } = useCrmChoices()
  const [tab, setTab] = useState('Activity')
  const [logging, setLogging] = useState(false)
  const [converting, setConverting] = useState(false)
  const [merging, setMerging] = useState(false)

  if (isLoading) return <DetailSkeleton />
  if (isError || !lead) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center">
        <div className="text-tx-2">This lead no longer exists.</div>
        <Link to="/leads" className="mt-3 inline-block text-sm text-brand hover:underline">
          Back to Leads
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <Header
        lead={lead}
        choices={choices}
        canManage={canManage}
        canConvert={canConvert}
        onLogCall={() => setLogging(true)}
        onConvert={() => setConverting(true)}
        onMerge={() => setMerging(true)}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* CRM state is the working surface, so it sits in the column the eye
            lands on; the read-only business facts sit under it. */}
        <div className="flex flex-col gap-5 lg:col-span-1">
          <CrmPanel lead={lead} choices={choices} canManage={canManage} />
          <BusinessPanel lead={lead} choices={choices} canManage={canManage} />
        </div>

        <div className="lg:col-span-2">
          <div className="mb-3 flex gap-1 rounded-ctl border border-line bg-surface p-1">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 rounded-ctl px-3 py-1.5 text-sm transition ${
                  tab === t ? 'bg-brand text-white' : 'text-tx-2 hover:text-tx'
                }`}
              >
                {t}
                {t === 'Calls' && lead.calls?.length > 0 && (
                  <span className="ml-1.5 text-xs opacity-70">{lead.calls.length}</span>
                )}
              </button>
            ))}
          </div>

          <div className="rounded-card border border-line bg-surface p-5">
            {tab === 'Activity' && <LeadTimeline activities={lead.activities} />}
            {tab === 'Calls' && <CallsTab lead={lead} choices={choices} />}
            {tab === 'Details' && <MetaTab lead={lead} />}
          </div>
        </div>
      </div>

      {logging && (
        <LogCallModal leadId={lead.id} choices={choices} onClose={() => setLogging(false)} />
      )}

      {converting && (
        <ConvertModal lead={lead} choices={choices} onClose={() => setConverting(false)} />
      )}

      {merging && <MergeModal lead={lead} onClose={() => setMerging(false)} />}
    </div>
  )
}

function Header({ lead, choices, canManage, canConvert, onLogCall, onConvert, onMerge }) {
  const navigate = useNavigate()
  const del = useDeleteLead()

  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        <Link
          to="/leads"
          className="mt-1 rounded-ctl border border-line p-1.5 text-tx-3 hover:border-brand hover:text-brand"
        >
          <ArrowLeft size={15} />
        </Link>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-head text-2xl font-bold text-tx">{lead.business_name}</h1>
            {lead.is_converted && (
              <Link to={`/merchants/${lead.converted_merchant}`}>
                <Badge tone="success">Converted →</Badge>
              </Link>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-tx-3">
            <span>{titleCase(lead.lead_type)} lead</span>
            <span>·</span>
            <span>{labelFor(choices, KIND.SOURCE, lead.source)}</span>
            <span>·</span>
            <span>Added {shortDate(lead.created_at)}</span>
            <span>·</span>
            <span>
              by {lead.created_by ? lead.created_by.name || lead.created_by.email : 'System'}
            </span>
          </div>
        </div>
      </div>

      {canManage && (
        <div className="flex items-center gap-2">
          {/* Convert is the pipeline's whole point, so it is the loudest thing
              here — until it has happened, after which it would be a lie. */}
          {canConvert && !lead.is_converted && (
            <button
              onClick={onConvert}
              className="flex items-center gap-2 rounded-ctl bg-success px-3 py-2 text-sm font-semibold text-bg transition hover:opacity-90"
            >
              <Building2 size={15} /> Convert to Merchant
            </button>
          )}
          <button
            onClick={onLogCall}
            className="flex items-center gap-2 rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand"
          >
            <PhoneCall size={15} /> Log Call
          </button>
          {/* Merge only makes sense before conversion — a converted lead is a
              merchant now and folding another into it would strand that link. */}
          {!lead.is_converted && (
            <button
              onClick={onMerge}
              className="rounded-ctl border border-line p-2 text-tx-3 hover:border-brand hover:text-brand"
              aria-label="Merge duplicates"
              title="Merge duplicates"
            >
              <GitMerge size={15} />
            </button>
          )}
          <button
            onClick={() => {
              if (window.confirm(`Delete the lead for ${lead.business_name}? This cannot be undone.`)) {
                del.mutate(lead.id, { onSuccess: () => navigate('/leads') })
              }
            }}
            disabled={del.isPending}
            className="rounded-ctl border border-line p-2 text-tx-3 hover:border-danger hover:text-danger disabled:opacity-50"
            aria-label="Delete lead"
          >
            <Trash2 size={15} />
          </button>
        </div>
      )}
    </div>
  )
}

// Every CRM field is a live dropdown: changing one PATCHes immediately and the
// backend writes the timeline entry. No Save button, because there is no draft
// state to save — and a half-edited lead that was never saved is worse than one
// that changed a field too eagerly.
function CrmPanel({ lead, choices, canManage }) {
  const update = useUpdateLead()
  const { data: salesUsers } = useSalesUsers()
  const tone = scoreTone(lead.lead_score)

  const set = (field) => (e) => {
    const value = e.target.value
    update.mutate({ id: lead.id, [field]: value === '__none__' ? null : value })
  }

  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-head text-sm font-semibold text-tx">CRM</h2>
        {update.isPending && <Loader2 size={13} className="animate-spin text-tx-3" />}
      </div>

      <div className="mb-4">
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className="text-xs text-tx-3">Lead score</span>
          <span className={`font-num text-lg ${tone.text}`}>{lead.lead_score}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-surface-3">
          <div
            className={`h-full rounded-full transition-all ${tone.bar}`}
            style={{ width: `${lead.lead_score}%` }}
          />
        </div>
        <div className="mt-1.5 text-xs text-tx-3">
          Calculated from priority, temperature, activity and milestones.
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <Row label="Status">
          <Picker value={lead.status} onChange={set('status')} disabled={!canManage}>
            {optionsFor(choices, KIND.STATUS).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Picker>
        </Row>
        <Row label="Priority">
          <Picker value={lead.priority} onChange={set('priority')} disabled={!canManage}>
            {optionsFor(choices, KIND.PRIORITY).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Picker>
        </Row>
        <Row label="Temperature">
          <Picker value={lead.temperature} onChange={set('temperature')} disabled={!canManage}>
            {optionsFor(choices, KIND.TEMPERATURE).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Picker>
        </Row>
        <Row label="Assigned">
          <Picker
            value={lead.assigned_sales?.id ?? '__none__'}
            onChange={set('assigned_sales')}
            disabled={!canManage}
          >
            <option value="__none__">Unassigned</option>
            {(salesUsers ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name || a.email}
              </option>
            ))}
          </Picker>
        </Row>
        <Row label="Next action">
          <Picker value={lead.next_action ?? ''} onChange={set('next_action')} disabled={!canManage}>
            <option value="">—</option>
            {optionsFor(choices, KIND.NEXT_ACTION).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Picker>
        </Row>
        <Row label="Expected plan">
          <Picker
            value={lead.expected_plan ?? ''}
            onChange={set('expected_plan')}
            disabled={!canManage}
          >
            <option value="">—</option>
            {optionsFor(choices, KIND.EXPECTED_PLAN).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </Picker>
        </Row>
      </div>

      <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4 text-xs">
        <Fact label="Next follow-up" value={lead.next_follow_up_at ? fromNow(lead.next_follow_up_at) : '—'} />
        <Fact label="Last contact" value={lead.last_contact_at ? fromNow(lead.last_contact_at) : 'Never'} />
      </div>
    </div>
  )
}

function BusinessPanel({ lead, choices, canManage }) {
  const links = [
    { Icon: Phone, label: lead.phone, href: lead.phone && `tel:${lead.phone}` },
    { Icon: MessageCircle, label: lead.whatsapp, href: lead.whatsapp && `https://wa.me/${lead.whatsapp.replace(/\D/g, '')}` },
    { Icon: Mail, label: lead.email, href: lead.email && `mailto:${lead.email}` },
    { Icon: Instagram, label: lead.instagram, href: toUrl(lead.instagram, 'https://instagram.com/') },
    { Icon: Facebook, label: lead.facebook, href: toUrl(lead.facebook, 'https://facebook.com/') },
    { Icon: Globe, label: lead.website, href: lead.website },
    { Icon: MapPin, label: lead.google_maps_url && 'Google Maps', href: lead.google_maps_url },
  ].filter((l) => l.label)

  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <h2 className="mb-4 font-head text-sm font-semibold text-tx">Business</h2>

      <div className="mb-4">
        <LeadLogo lead={lead} canManage={canManage} />
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-sm text-tx">
          <Building2 size={14} className="text-tx-3" />
          {lead.name || '—'}
        </div>
        {links.map(({ Icon, label, href }, i) => (
          <a
            key={i}
            href={href || undefined}
            target={href?.startsWith('http') ? '_blank' : undefined}
            rel="noreferrer"
            className="flex items-center gap-2 truncate text-sm text-tx-2 hover:text-brand"
          >
            <Icon size={14} className="shrink-0 text-tx-3" />
            <span className="truncate">{label}</span>
          </a>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4 text-xs">
        <Fact label="Area" value={lead.area || '—'} />
        <Fact label="Category" value={labelFor(choices, KIND.CATEGORY, lead.category)} />
        <Fact label="Address" value={lead.address || '—'} />
      </div>

      {lead.notes && (
        <div className="mt-4 border-t border-line pt-4">
          <div className="mb-1 text-xs text-tx-3">Notes</div>
          <p className="whitespace-pre-wrap text-sm text-tx-2">{lead.notes}</p>
        </div>
      )}
    </div>
  )
}

function CallsTab({ lead, choices }) {
  if (!lead.calls?.length) {
    return (
      <div className="py-10 text-center">
        <PhoneCall size={22} className="mx-auto mb-2 text-tx-3" />
        <div className="text-sm text-tx-2">No calls logged yet.</div>
      </div>
    )
  }

  return (
    <ul className="flex flex-col gap-3">
      {lead.calls.map((c) => (
        <li key={c.id} className="rounded-ctl border border-line bg-bg p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Badge>{titleCase(c.result)}</Badge>
              <span className="text-xs text-tx-3">
                {labelFor(choices, KIND.CONTACT_METHOD, c.contact_method)}
                {c.duration_seconds > 0 && ` · ${Math.round(c.duration_seconds / 60)} min`}
              </span>
            </div>
            <span className="text-xs text-tx-3" title={new Date(c.called_at).toLocaleString()}>
              {fromNow(c.called_at)}
            </span>
          </div>
          {c.notes && <p className="mt-2 whitespace-pre-wrap text-sm text-tx-2">{c.notes}</p>}
          <div className="mt-2 text-xs text-tx-3">{c.logged_by_label || 'Unknown'}</div>
        </li>
      ))}
    </ul>
  )
}

function MetaTab({ lead }) {
  return (
    <div className="flex flex-col gap-2 text-xs">
      <Fact label="Lead type" value={titleCase(lead.lead_type)} />
      <Fact label="Created by" value={lead.created_by ? lead.created_by.name || lead.created_by.email : 'System'} />
      <Fact label="Created at" value={new Date(lead.created_at).toLocaleString()} />
      <Fact label="Updated at" value={new Date(lead.updated_at).toLocaleString()} />
      <Fact label="First contacted" value={lead.contacted_at ? new Date(lead.contacted_at).toLocaleString() : 'Never'} />
      <Fact label="Expected revenue" value={lead.expected_revenue ?? '—'} />
      <Fact label="Converted" value={lead.converted_at ? new Date(lead.converted_at).toLocaleString() : 'No'} />
    </div>
  )
}

// Instagram and Facebook are stored as a handle *or* a URL, since sales paste
// whichever they have. Only prefix the bare handle.
function toUrl(value, base) {
  if (!value) return null
  return value.startsWith('http') ? value : base + value.replace(/^@/, '')
}

function Row({ label, children }) {
  return (
    <label className="flex items-center justify-between gap-3">
      <span className="text-xs text-tx-3">{label}</span>
      {children}
    </label>
  )
}

function Picker({ children, ...props }) {
  return (
    <select
      {...props}
      className="w-40 rounded-ctl border border-line bg-bg px-2 py-1.5 text-sm text-tx focus:border-brand focus:outline-none disabled:opacity-60"
    >
      {children}
    </select>
  )
}

function Fact({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-tx-3">{label}</span>
      <span className="text-right text-tx-2">{value}</span>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <div className="h-8 w-64 animate-pulse rounded bg-surface-2" />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="h-80 animate-pulse rounded-card bg-surface" />
        <div className="h-80 animate-pulse rounded-card bg-surface lg:col-span-2" />
      </div>
    </div>
  )
}
