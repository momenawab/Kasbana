// Customers list (spec §14) — debounced search, segment/status filter chips,
// cursor-paginated table, CSV export gated by can('export'). Row → profile.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Users, Download } from 'lucide-react'
import { useCustomers } from './api'
import { usePlan } from '../../hooks/usePlan'
import Table from '../../components/Table'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import EmptyState from '../../components/EmptyState'
import { Input } from '../../components/Field'
import { arDigits, fromNow } from '../../lib/format'

const SEGMENTS = ['', 'lapsed', 'reward_ready']

export default function CustomersList() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { can, requireFeature } = usePlan()
  const lang = i18n.language

  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [segment, setSegment] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setDebounced(search), 300)
    return () => clearTimeout(id)
  }, [search])

  const { data, isLoading } = useCustomers({ search: debounced, segment })
  const rows = data?.results ?? []

  function exportCsv() {
    if (!requireFeature('export')) return // opens UpgradeDrawer when gated
    const header = ['name', 'phone', 'card', 'stamps', 'status', 'joined']
    const lines = rows.map((r) =>
      [r.customer_name, r.customer_phone, r.card_name, `${r.stamp_count}/${r.stamps_required}`, r.status, r.enrolled_at].join(',')
    )
    const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'customers.csv'
    a.click()
  }

  const columns = [
    { key: 'customer_name', label: t('customers.name'), render: (r) => r.customer_name || '—' },
    { key: 'customer_phone', label: t('customers.phone'), render: (r) => <span dir="ltr">{r.customer_phone}</span> },
    { key: 'card_name', label: t('customers.card') },
    {
      key: 'stamps',
      label: t('customers.stamps'),
      render: (r) => <span className="font-num">{arDigits(`${r.stamp_count}/${r.stamps_required}`, lang)}</span>,
    },
    { key: 'status', label: t('customers.statusCol'), render: (r) => <Badge tone="teal">{r.status}</Badge> },
    {
      key: 'last_event_at',
      label: t('customers.lastVisit'),
      render: (r) => (r.last_event_at ? fromNow(r.last_event_at, lang) : '—'),
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-ink">{t('customers.title')}</h1>
        <Button variant="ghost" iconStart={Download} onClick={exportCsv} disabled={!can('export')}>
          {t('customers.export')}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[200px] flex-1">
          <Input
            name="search"
            placeholder={t('customers.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1">
          {SEGMENTS.map((s) => (
            <button
              key={s || 'all'}
              onClick={() => setSegment(s)}
              className={`rounded-full px-3 py-1.5 text-sm ${
                segment === s ? 'bg-amber text-ink font-semibold' : 'bg-paper text-tx-2'
              }`}
            >
              {t(`customers.segment.${s || 'all'}`)}
            </button>
          ))}
        </div>
      </div>

      <Table
        columns={columns}
        rows={rows}
        loading={isLoading}
        onRowClick={(r) => navigate(`/customers/${r.id}`)}
        emptyState={
          <EmptyState icon={Users} title={t('customers.emptyTitle')} body={t('customers.emptyBody')} />
        }
      />
    </div>
  )
}
