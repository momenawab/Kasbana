import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, Apple, Smartphone } from 'lucide-react'
import { useMerchant } from './api'
import Badge from '../../components/Badge'
import { num, shortDate, statusTone } from '../../lib/format'
import SubscriptionTab from './SubscriptionTab'
import MerchantBillingTab from './MerchantBillingTab'
import SupportTab from './SupportTab'
import ActivityTab from './ActivityTab'

const TABS = [
  { key: 'overview', label: 'Overview', ready: true },
  { key: 'subscription', label: 'Subscription', ready: true },
  { key: 'billing', label: 'Billing', ready: true },
  { key: 'support', label: 'Support', ready: true },
  { key: 'activity', label: 'Activity', ready: true },
]

function Stat({ label, value }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="text-xs text-tx-3">{label}</div>
      <div className="mt-1 font-num text-2xl text-tx">{value}</div>
    </div>
  )
}

export default function MerchantDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: m, isLoading } = useMerchant(id)
  const [tab, setTab] = useState('overview')

  if (isLoading || !m) {
    return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
  }

  const usage = m.usage || {}

  return (
    <div className="flex flex-col gap-5">
      <button
        onClick={() => navigate('/merchants')}
        className="flex w-fit items-center gap-2 text-sm text-tx-2 hover:text-tx"
      >
        <ArrowLeft size={16} /> Merchants
      </button>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-card border border-line bg-surface p-5">
        <div className="flex items-center gap-3">
          {m.logo_url ? (
            <img src={m.logo_url} alt="" className="h-12 w-12 rounded-ctl object-cover" />
          ) : (
            <div
              className="flex h-12 w-12 items-center justify-center rounded-ctl font-head font-bold"
              style={{ background: m.color_bg || '#26344A', color: m.color_fg || '#E6EAF0' }}
            >
              {m.name?.[0] || '?'}
            </div>
          )}
          <div>
            <h1 className="font-head text-2xl font-bold text-tx">{m.name}</h1>
            <div className="mt-1 flex items-center gap-2 text-sm text-tx-3">
              <span>{m.slug}</span>
              <Badge tone="brand">{m.plan}</Badge>
              <Badge tone={statusTone(m.billing_status)}>{m.billing_status}</Badge>
            </div>
          </div>
        </div>
        <div className="text-right text-sm text-tx-2">
          <div>Joined {shortDate(m.created_at)}</div>
          {m.trial_ends_at && <div className="text-tx-3">Trial ends {shortDate(m.trial_ends_at)}</div>}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => t.ready && setTab(t.key)}
            className={
              'relative px-3 py-2 text-sm ' +
              (tab === t.key ? 'text-brand' : 'text-tx-3 hover:text-tx-2') +
              (t.ready ? '' : ' cursor-default')
            }
          >
            {t.label}
            {!t.ready && <span className="ml-1 text-[10px] text-tx-3">P{t.phase}</span>}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-brand" />}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="flex flex-col gap-4">
          {/* Usage stats */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Customers" value={num(usage.customers)} />
            <Stat label="Cards" value={num(usage.cards)} />
            <Stat label="Staff" value={num(usage.staff)} />
            <Stat label="Locations" value={num(usage.locations)} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Owner + contact */}
            <div className="rounded-card border border-line bg-surface p-4">
              <h2 className="mb-3 font-head font-semibold text-tx">Owner &amp; contact</h2>
              <dl className="flex flex-col gap-2 text-sm">
                <Row label="Owner" value={m.owner?.name || '—'} />
                <Row label="Owner email" value={m.owner?.email || '—'} />
                <Row label="Contact email" value={m.contact?.email || '—'} />
                <Row label="Contact phone" value={m.contact?.name || '—'} />
                <Row label="Legal name" value={m.legal_name || '—'} />
              </dl>
            </div>

            {/* Wallet passes */}
            <div className="rounded-card border border-line bg-surface p-4">
              <h2 className="mb-3 font-head font-semibold text-tx">Wallet passes</h2>
              <div className="flex gap-6">
                <div className="flex items-center gap-2">
                  <Apple size={18} className="text-tx-2" />
                  <span className="font-num text-xl text-tx">{num(m.wallet?.apple)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Smartphone size={18} className="text-tx-2" />
                  <span className="font-num text-xl text-tx">{num(m.wallet?.google)}</span>
                </div>
              </div>
              {m.admin_meta?.internal_notes && (
                <p className="mt-4 border-t border-line pt-3 text-sm text-tx-2">
                  {m.admin_meta.internal_notes}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'subscription' && <SubscriptionTab merchantId={id} />}
      {tab === 'billing' && <MerchantBillingTab merchantId={id} />}
      {tab === 'support' && <SupportTab merchantId={id} merchantName={m.name} />}
      {tab === 'activity' && <ActivityTab merchantId={id} />}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-tx-3">{label}</dt>
      <dd className="text-right text-tx">{value}</dd>
    </div>
  )
}
