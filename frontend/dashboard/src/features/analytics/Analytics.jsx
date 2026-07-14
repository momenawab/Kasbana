// Analytics (spec §14) — DateRange filter + charts. Growth+ sees full charts;
// Starter (features.analytics === 'basic') sees summary KPIs + joins only, the
// rest locked behind the UpgradeDrawer. timeseries/retention/by_location are 1.6.
//
// Each panel carries an expand affordance: the grid stays compact enough to clear
// the fold, and the detail (per-day numbers, totals, CSV) lives in a modal so the
// page itself doesn't grow.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Lock, Maximize2 } from 'lucide-react'
import api from '../../lib/api'
import { usePlan } from '../../hooks/usePlan'
import KpiTile from '../../components/KpiTile'
import { ChartLine, ChartBar, ChartDonut } from '../../components/Charts'
import DateRange from '../../components/DateRange'
import Button from '../../components/Button'
import { Modal } from '../../components/Modal'
import { gating } from '../../lib/gating'
import { arDigits } from '../../lib/format'

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
const CHART_H_LG = 380

const REDEMPTION_COLOR = '#D43DCF'

// `new Date('2026-07-14')` parses as UTC midnight and then renders in local time,
// which lands on the 13th anywhere west of Greenwich. Build the date locally.
function parseDay(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

function fmtDay(iso, lang, opts) {
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-EG' : 'en-GB', opts).format(parseDay(iso))
}

const shortDay = (iso, lang) => fmtDay(iso, lang, { day: 'numeric', month: 'short' })
const longDay = (iso, lang) =>
  fmtDay(iso, lang, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })

// Everything the detail view shows is derived from the points the chart already
// has — no extra endpoint.
function seriesStats(points) {
  const values = points.map((p) => Number(p.value) || 0)
  const total = values.reduce((a, b) => a + b, 0)
  const days = values.length
  const peak = points.reduce(
    (best, p) => ((Number(p.value) || 0) > best.value ? { date: p.date, value: Number(p.value) } : best),
    { date: null, value: 0 }
  )
  return {
    total,
    days,
    avg: days ? total / days : 0,
    activeDays: values.filter((v) => v > 0).length,
    peak: peak.value > 0 ? peak : null,
  }
}

function downloadCsv(filename, header, rows) {
  const escape = (cell) => {
    const s = String(cell ?? '')
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [header, ...rows].map((r) => r.map(escape).join(',')).join('\r\n')
  // BOM so Excel reads the UTF-8 (and Arabic headers) correctly.
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-card border border-line bg-paper p-3">
      <div className="text-xs text-tx-2">{label}</div>
      <div className="font-num font-head text-xl font-bold text-tx">{value}</div>
      {sub && <div className="text-xs text-tx-3">{sub}</div>}
    </div>
  )
}

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

function Panel({ title, onExpand, children }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="font-head text-sm font-semibold text-tx">{title}</h3>
        <button
          onClick={onExpand}
          aria-label={`${t('analytics.expand')} — ${title}`}
          title={t('analytics.expand')}
          className="rounded-ctl p-1 text-tx-3 transition hover:bg-paper hover:text-tx"
        >
          <Maximize2 size={16} />
        </button>
      </div>
      {children}
    </div>
  )
}

// Per-day breakdown behind a timeseries chart: totals + every bucket, so the
// numbers the small chart only hints at are actually readable.
function SeriesDetail({ points, title, lang, chart }) {
  const { t } = useTranslation()
  const stats = seriesStats(points)
  const n = (v) => arDigits(v, lang)

  if (!points.length) return <p className="py-8 text-center text-tx-3">{t('analytics.noData')}</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label={t('analytics.total')} value={n(stats.total)} />
        <Stat label={t('analytics.dailyAvg')} value={n(stats.avg.toFixed(1))} />
        <Stat
          label={t('analytics.peakDay')}
          value={stats.peak ? n(stats.peak.value) : '—'}
          sub={stats.peak ? shortDay(stats.peak.date, lang) : undefined}
        />
        <Stat
          label={t('analytics.activeDays')}
          value={`${n(stats.activeDays)} / ${n(stats.days)}`}
        />
      </div>

      {chart(CHART_H_LG)}

      <div className="max-h-64 overflow-y-auto rounded-card border border-line">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-line text-tx-2">
              <th className="px-4 py-2 text-start font-semibold">{t('analytics.date')}</th>
              <th className="px-4 py-2 text-end font-semibold">{title}</th>
            </tr>
          </thead>
          <tbody>
            {[...points].reverse().map((p) => (
              <tr key={p.date} className="border-b border-line last:border-0">
                <td className="px-4 py-2 text-tx">{longDay(p.date, lang)}</td>
                <td className="px-4 py-2 text-end font-num text-tx">{n(p.value ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function DonutDetail({ data, lang, chart }) {
  const { t } = useTranslation()
  const total = data.reduce((sum, d) => sum + (Number(d.value) || 0), 0)
  const n = (v) => arDigits(v, lang)
  const share = (v) => (total ? `${n(Math.round((v / total) * 100))}%` : '—')

  if (!total) return <p className="py-8 text-center text-tx-3">{t('analytics.noData')}</p>

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={t('analytics.total')} value={n(total)} />
        {data.map((d) => (
          <Stat key={d.name} label={d.name} value={n(d.value)} sub={share(d.value)} />
        ))}
      </div>

      {chart(CHART_H_LG)}

      <div className="overflow-hidden rounded-card border border-line">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-tx-2">
              <th className="px-4 py-2 text-start font-semibold">{t('analytics.wallet')}</th>
              <th className="px-4 py-2 text-end font-semibold">{t('analytics.count')}</th>
              <th className="px-4 py-2 text-end font-semibold">{t('analytics.share')}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.name} className="border-b border-line last:border-0">
                <td className="px-4 py-2 text-tx">{d.name}</td>
                <td className="px-4 py-2 text-end font-num text-tx">{n(d.value)}</td>
                <td className="px-4 py-2 text-end font-num text-tx-2">{share(d.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Analytics() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { entitlements } = usePlan()
  const full = entitlements?.features?.analytics === 'full' || entitlements?.plan === 'trial'
  const [range, setRange] = useState({ from: '', to: '' })
  const [expanded, setExpanded] = useState(null)

  const { data: summary } = useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: async () => (await api.get('/analytics/summary')).data,
  })
  const joins = useSeries('joins', range)
  const stamps = useSeries('stamps', range, full)
  const redemptions = useSeries('redemptions', range, full)

  const walletSplit = [
    { name: 'Apple', value: summary?.apple_count ?? 0 },
    { name: 'Google', value: summary?.google_count ?? 0 },
  ]

  // One descriptor per panel: the small grid and the expanded modal render the
  // same chart, so they can't drift apart.
  const tsProps = {
    labelFormatter: (d) => longDay(d, lang),
    tickFormatter: (d) => shortDay(d, lang),
  }
  const CHARTS = {
    joins: {
      title: t('analytics.joins'),
      points: joins.data ?? [],
      chart: (h) => (
        <ChartLine data={joins.data ?? []} height={h} name={t('analytics.joins')} {...tsProps} />
      ),
    },
    stamps: {
      title: t('analytics.stamps'),
      points: stamps.data ?? [],
      chart: (h) => (
        <ChartBar data={stamps.data ?? []} height={h} name={t('analytics.stamps')} {...tsProps} />
      ),
    },
    redemptions: {
      title: t('analytics.redemptions'),
      points: redemptions.data ?? [],
      chart: (h) => (
        <ChartBar
          data={redemptions.data ?? []}
          height={h}
          color={REDEMPTION_COLOR}
          name={t('analytics.redemptions')}
          {...tsProps}
        />
      ),
    },
    walletSplit: {
      title: t('analytics.walletSplit'),
      donut: walletSplit,
      chart: (h) => <ChartDonut data={walletSplit} height={h} />,
    },
  }

  const active = expanded ? CHARTS[expanded] : null

  function exportCsv() {
    if (!active) return
    const stamp = new Date().toISOString().slice(0, 10)
    if (active.donut) {
      downloadCsv(
        `stampn-wallet-split-${stamp}.csv`,
        [t('analytics.wallet'), t('analytics.count')],
        active.donut.map((d) => [d.name, d.value])
      )
    } else {
      downloadCsv(
        `stampn-${expanded}-${stamp}.csv`,
        [t('analytics.date'), active.title],
        active.points.map((p) => [p.date, p.value ?? 0])
      )
    }
  }

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
        <Panel title={CHARTS.joins.title} onExpand={() => setExpanded('joins')}>
          {CHARTS.joins.chart(CHART_H)}
        </Panel>

        {/* Gated for Starter */}
        {['stamps', 'redemptions', 'walletSplit'].map((key) =>
          full ? (
            <Panel key={key} title={CHARTS[key].title} onExpand={() => setExpanded(key)}>
              {CHARTS[key].chart(CHART_H)}
            </Panel>
          ) : (
            <LockedCard key={key} title={CHARTS[key].title} />
          )
        )}
      </div>

      <Modal
        open={!!active}
        onClose={() => setExpanded(null)}
        title={active?.title ?? ''}
        size="xl"
        headerExtra={
          active && (
            <Button size="sm" variant="ghost" onClick={exportCsv}>
              {t('analytics.exportCsv')}
            </Button>
          )
        }
      >
        {active &&
          (active.donut ? (
            <DonutDetail data={active.donut} lang={lang} chart={active.chart} />
          ) : (
            <SeriesDetail
              points={active.points}
              title={active.title}
              lang={lang}
              chart={active.chart}
            />
          ))}
      </Modal>
    </div>
  )
}
