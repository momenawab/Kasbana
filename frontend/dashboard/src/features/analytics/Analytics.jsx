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

// Every panel on this page is one chart tall, so the chart height is what decides
// whether the page clears the fold. Keep them in step.
const CHART_H = 180

function LockedCard({ title }) {
  const { t } = useTranslation()
  return (
    <button
      onClick={() => gating.open('analytics')}
      className="flex h-full min-h-[180px] flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line bg-surface text-tx-3"
    >
      <Lock size={22} />
      <span className="font-head font-semibold text-tx">{title}</span>
      <span className="text-xs">{t('analytics.locked')}</span>
    </button>
  )
}

function Panel({ title, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <h3 className="mb-2 font-head text-sm font-semibold text-tx">{title}</h3>
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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-head text-2xl font-bold text-tx">{t('analytics.title')}</h1>
        <DateRange value={range} onChange={setRange} />
      </div>

      {/* Summary KPIs (all plans) — compact, so the charts below still clear the
          fold; the full-size tiles alone ran to 168px. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiTile
          compact
          label={t('overview.enrollments')}
          value={summary?.enrollments ?? 0}
          tone="violet"
        />
        <KpiTile
          compact
          label={t('overview.activeCards')}
          value={summary?.active_cards ?? 0}
          tone="teal"
        />
        <KpiTile
          compact
          label={t('overview.redemptions')}
          value={summary?.redemptions ?? 0}
          tone="fuchsia"
        />
        <KpiTile
          compact
          label={t('overview.repeatRate')}
          value={`${Math.round((summary?.repeat_rate ?? 0) * 100)}%`}
          tone="slate"
        />
      </div>

      {/* One row of four on a wide screen: stacked 2×2 the charts alone were
          628px tall, which no laptop viewport could show alongside the KPIs. */}
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        {/* Joins — available on all plans */}
        <Panel title={t('analytics.joins')}>
          <ChartLine data={joins.data ?? []} height={CHART_H} />
        </Panel>

        {/* Gated for Starter */}
        {full ? (
          <Panel title={t('analytics.stamps')}>
            <ChartBar data={stamps.data ?? []} height={CHART_H} />
          </Panel>
        ) : (
          <LockedCard title={t('analytics.stamps')} />
        )}
        {full ? (
          <Panel title={t('analytics.redemptions')}>
            <ChartBar data={redemptions.data ?? []} height={CHART_H} color="#D43DCF" />
          </Panel>
        ) : (
          <LockedCard title={t('analytics.redemptions')} />
        )}
        {full ? (
          <Panel title={t('analytics.walletSplit')}>
            <ChartDonut
              height={CHART_H}
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
