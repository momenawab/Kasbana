// Analytics (spec §14) — DateRange filter + charts. Growth+ sees full charts;
// Starter (features.analytics === 'basic') sees summary KPIs + joins only, the
// rest locked behind the UpgradeDrawer. timeseries/retention/by_location are 1.6.
//
// Each panel carries an expand affordance: the grid stays compact enough to clear
// the fold, and the detail (per-day numbers, totals, CSV) lives in a modal so the
// page itself doesn't grow. The expanded view opens on the page's date range and
// then keeps its own copy of it — see ExpandedPanel.
import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
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

// keepPreviousData: retuning the date range swaps the query key, and without it the
// chart would blank out to "no data" on every keystroke in the date input.
function useSeries(metric, range, enabled = true) {
  const qs = new URLSearchParams({ metric, ...range }).toString()
  return useQuery({
    queryKey: ['analytics', 'ts', metric, range],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      try {
        return (await api.get(`/analytics/timeseries?${qs}`)).data.points ?? []
      } catch {
        return []
      }
    },
  })
}

// Apple/Google counts for passes added inside the range. /analytics/summary carries
// the same two numbers but all-time, so it only stands in for a backend that predates
// the scoped endpoint.
function useWalletSplit(range, enabled = true) {
  const qs = new URLSearchParams(range).toString()
  return useQuery({
    queryKey: ['analytics', 'wallet', range],
    enabled,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      try {
        return (await api.get(`/analytics/wallet_split?${qs}`)).data
      } catch {
        return (await api.get('/analytics/summary')).data
      }
    },
  })
}

const walletPoints = (data) => [
  { name: 'Apple', value: data?.apple_count ?? 0 },
  { name: 'Google', value: data?.google_count ?? 0 },
]

// Every panel on this page is one chart tall, so the chart height is what decides
// whether the page clears the fold. Keep them in step. The expanded chart instead
// takes '100%' of whatever the modal's flex column leaves it.
const CHART_H = 180

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

function EmptyDetail() {
  const { t } = useTranslation()
  return (
    <p className="flex flex-1 items-center justify-center text-tx-3">{t('analytics.noData')}</p>
  )
}

// A detail view stacks three blocks in the modal's flex column: fixed-height stats,
// the chart taking every pixel left over, and a table capped so it can never push the
// chart out of view. Between them the whole thing fits 90vh without scrolling.
//
// recharts measures its own parent, so the chart hangs in an absolutely-positioned box:
// that way its height is dictated by the flex column and can never feed back into it.
function ChartSlot({ children }) {
  return (
    <div className="relative min-h-[200px] flex-1">
      <div className="absolute inset-0">{children}</div>
    </div>
  )
}

const TABLE_SLOT = 'max-h-[26vh] shrink-0 overflow-y-auto rounded-card border border-line'

// Per-day breakdown behind a timeseries chart: totals + every bucket, so the
// numbers the small chart only hints at are actually readable.
function SeriesDetail({ points, title, lang, chart }) {
  const { t } = useTranslation()
  const stats = seriesStats(points)
  const n = (v) => arDigits(v, lang)

  if (!points.length) return <EmptyDetail />

  return (
    <>
      <div className="grid shrink-0 gap-3 sm:grid-cols-4">
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

      <ChartSlot>{chart}</ChartSlot>

      <div className={TABLE_SLOT}>
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
    </>
  )
}

function DonutDetail({ data, lang, chart }) {
  const { t } = useTranslation()
  const total = data.reduce((sum, d) => sum + (Number(d.value) || 0), 0)
  const n = (v) => arDigits(v, lang)
  const share = (v) => (total ? `${n(Math.round((v / total) * 100))}%` : '—')

  if (!total) return <EmptyDetail />

  return (
    <>
      <div className="grid shrink-0 gap-3 sm:grid-cols-3">
        <Stat label={t('analytics.total')} value={n(total)} />
        {data.map((d) => (
          <Stat key={d.name} label={d.name} value={n(d.value)} sub={share(d.value)} />
        ))}
      </div>

      <ChartSlot>{chart}</ChartSlot>

      <div className={TABLE_SLOT}>
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
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
    </>
  )
}

// Which chart each panel draws. `donut` is the one panel not backed by a timeseries.
const PANELS = {
  joins: { titleKey: 'analytics.joins', Chart: ChartLine },
  stamps: { titleKey: 'analytics.stamps', Chart: ChartBar },
  redemptions: { titleKey: 'analytics.redemptions', Chart: ChartBar, color: REDEMPTION_COLOR },
  walletSplit: { titleKey: 'analytics.walletSplit', donut: true },
}

// The expanded view. It mounts when a panel is expanded and unmounts on close, which
// is what seeds its date range from the page's — from then on the two are independent,
// so narrowing the range in here leaves the page's own filter alone. It also refetches
// against its own range rather than reusing the page's points.
function ExpandedPanel({ metric, initialRange, onClose }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const [range, setRange] = useState(initialRange)

  const panel = PANELS[metric]
  const title = t(panel.titleKey)
  const isDonut = !!panel.donut

  const series = useSeries(metric, range, !isDonut)
  const wallet = useWalletSplit(range, isDonut)

  const points = series.data ?? []
  const donut = walletPoints(wallet.data)

  const Chart = panel.Chart
  const chart = isDonut ? (
    <ChartDonut data={donut} height="100%" />
  ) : (
    <Chart
      data={points}
      height="100%"
      color={panel.color}
      name={title}
      labelFormatter={(d) => longDay(d, lang)}
      tickFormatter={(d) => shortDay(d, lang)}
    />
  )

  function exportCsv() {
    const stamp = new Date().toISOString().slice(0, 10)
    if (isDonut) {
      downloadCsv(
        `stampn-wallet-split-${stamp}.csv`,
        [t('analytics.wallet'), t('analytics.count')],
        donut.map((d) => [d.name, d.value])
      )
    } else {
      downloadCsv(
        `stampn-${metric}-${stamp}.csv`,
        [t('analytics.date'), title],
        points.map((p) => [p.date, p.value ?? 0])
      )
    }
  }

  return (
    <Modal open onClose={onClose} title={title} size="xl" fitViewport>
      <div className="flex min-h-full flex-col gap-3">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <DateRange value={range} onChange={setRange} />
          <Button size="sm" variant="ghost" onClick={exportCsv}>
            {t('analytics.exportCsv')}
          </Button>
        </div>

        {isDonut ? (
          <DonutDetail data={donut} lang={lang} chart={chart} />
        ) : (
          <SeriesDetail points={points} title={title} lang={lang} chart={chart} />
        )}
      </div>
    </Modal>
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
  const wallet = useWalletSplit(range, full)

  const tsProps = {
    labelFormatter: (d) => longDay(d, lang),
    tickFormatter: (d) => shortDay(d, lang),
  }
  const series = { joins: joins.data ?? [], stamps: stamps.data ?? [], redemptions: redemptions.data ?? [] }

  function preview(key) {
    const panel = PANELS[key]
    if (panel.donut) return <ChartDonut data={walletPoints(wallet.data)} height={CHART_H} />
    const Chart = panel.Chart
    return (
      <Chart
        data={series[key]}
        height={CHART_H}
        color={panel.color}
        name={t(panel.titleKey)}
        {...tsProps}
      />
    )
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
        <Panel title={t('analytics.joins')} onExpand={() => setExpanded('joins')}>
          {preview('joins')}
        </Panel>

        {/* Gated for Starter */}
        {['stamps', 'redemptions', 'walletSplit'].map((key) =>
          full ? (
            <Panel key={key} title={t(PANELS[key].titleKey)} onExpand={() => setExpanded(key)}>
              {preview(key)}
            </Panel>
          ) : (
            <LockedCard key={key} title={t(PANELS[key].titleKey)} />
          )
        )}
      </div>

      {expanded && (
        <ExpandedPanel
          key={expanded}
          metric={expanded}
          initialRange={range}
          onClose={() => setExpanded(null)}
        />
      )}
    </div>
  )
}
