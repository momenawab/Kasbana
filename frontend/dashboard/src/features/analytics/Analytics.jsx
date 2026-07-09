// Analytics (spec §14) — DateRange filter + charts. Growth+ sees full charts;
// Starter (features.analytics === 'basic') sees summary KPIs + joins only, the
// rest locked behind the UpgradeDrawer. timeseries/retention/by_location are 1.6.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Lock } from 'lucide-react'
import api from '../../lib/api'
import { usePlan } from '../../hooks/usePlan'
import KpiTile from '../../components/KpiTile'
import { ChartLine, ChartBar, ChartDonut } from '../../components/Charts'
import DateRange from '../../components/DateRange'
import { gating } from '../../lib/gating'

function useSeries(metric, range, enabled = true) {
  const qs = new URLSearchParams({ metric, ...range }).toString()
  return useQuery({
    queryKey: ['analytics', 'ts', metric, range],
    enabled,
    queryFn: async () => {
      try {
        return (await api.get(`/analytics/timeseries?${qs}`)).data.points ?? []
      } catch {
        return []
      }
    },
  })
}

function LockedCard({ title }) {
  const { t } = useTranslation()
  return (
    <button
      onClick={() => gating.open('analytics')}
      className="flex h-[260px] flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line bg-white text-tx-3"
    >
      <Lock size={22} />
      <span className="font-head font-semibold text-slate">{title}</span>
      <span className="text-xs">{t('analytics.locked')}</span>
    </button>
  )
}

function Panel({ title, children }) {
  return (
    <div className="rounded-card border border-line bg-white p-4">
      <h3 className="mb-2 font-head font-semibold text-slate">{title}</h3>
      {children}
    </div>
  )
}

export default function Analytics() {
  const { t } = useTranslation()
  const { entitlements } = usePlan()
  const full = entitlements?.features?.analytics === 'full' || entitlements?.plan === 'trial'
  const [range, setRange] = useState({ from: '', to: '' })

  const { data: summary } = useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: async () => (await api.get('/analytics/summary')).data,
  })
  const joins = useSeries('joins', range)
  const stamps = useSeries('stamps', range, full)
  const redemptions = useSeries('redemptions', range, full)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-head text-2xl font-bold text-slate">{t('analytics.title')}</h1>
        <DateRange value={range} onChange={setRange} />
      </div>

      {/* Summary KPIs (all plans) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiTile label={t('overview.enrollments')} value={summary?.enrollments ?? 0} tone="violet" />
        <KpiTile label={t('overview.activeCards')} value={summary?.active_cards ?? 0} tone="teal" />
        <KpiTile label={t('overview.redemptions')} value={summary?.redemptions ?? 0} tone="fuchsia" />
        <KpiTile
          label={t('overview.repeatRate')}
          value={`${Math.round((summary?.repeat_rate ?? 0) * 100)}%`}
          tone="slate"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Joins — available on all plans */}
        <Panel title={t('analytics.joins')}>
          <ChartLine data={joins.data ?? []} />
        </Panel>

        {/* Gated for Starter */}
        {full ? <Panel title={t('analytics.stamps')}><ChartBar data={stamps.data ?? []} /></Panel> : <LockedCard title={t('analytics.stamps')} />}
        {full ? <Panel title={t('analytics.redemptions')}><ChartBar data={redemptions.data ?? []} color="#C75D43" /></Panel> : <LockedCard title={t('analytics.redemptions')} />}
        {full ? (
          <Panel title={t('analytics.walletSplit')}>
            <ChartDonut
              data={[
                { name: 'Apple', value: summary?.apple_count ?? 0 },
                { name: 'Google', value: summary?.google_count ?? 0 },
              ]}
            />
          </Panel>
        ) : (
          <LockedCard title={t('analytics.walletSplit')} />
        )}
      </div>
    </div>
  )
}
