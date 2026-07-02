import { useState } from 'react'
import {
  Loader2,
  Download,
  TrendingUp,
  Users,
  Percent,
  Repeat,
  ArrowDownRight,
  Gift,
} from 'lucide-react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { useRevenue, downloadRevenueCsv } from './api'
import { useAuth } from '../../hooks/useAuth'
import { num } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

const COLORS = {
  brand: '#E0A23B',
  info: '#3B9FE0',
  success: '#2FBF87',
  grid: '#2A3648',
  axis: '#6B7A8D',
}

function egp(v) {
  if (v == null) return '—'
  return `${Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })} EGP`
}

function pct(v) {
  return v == null ? '—' : `${(Number(v) * 100).toFixed(1)}%`
}

function Kpi({ icon: Icon, label, value, hint }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex items-center gap-2 text-tx-3">
        <Icon size={15} />
        <span className="text-xs">{label}</span>
      </div>
      <div className="mt-2 font-num text-2xl text-tx">{value}</div>
      {hint && <div className="mt-1 text-xs text-tx-3">{hint}</div>}
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <h2 className="mb-4 font-head text-sm font-semibold text-tx">{title}</h2>
      {children}
    </div>
  )
}

const tooltipStyle = {
  contentStyle: { background: '#1B2637', border: '1px solid #2A3648', borderRadius: 9, color: '#E6EAF0' },
  labelStyle: { color: '#9AA7B8' },
}

export default function RevenueHome() {
  const { role } = useAuth()
  const [range, setRange] = useState({ from: '', to: '' })
  const params = {}
  if (range.from) params.from = range.from
  if (range.to) params.to = range.to
  const { data, isLoading, isError } = useRevenue(params)

  if (!FINANCE_ROLES.includes(role)) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
        Revenue analytics are restricted to Finance and Super-admin roles.
      </div>
    )
  }

  if (isLoading) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
  if (isError || !data) {
    return <div className="text-sm text-danger">Couldn’t load revenue analytics.</div>
  }

  const k = data.kpis

  return (
    <div className="flex flex-col gap-5">
      {/* Header + range + export */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-head text-2xl font-bold text-tx">Revenue &amp; Financials</h1>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs text-tx-3">
            From
            <input
              type="date"
              value={range.from}
              onChange={(e) => setRange({ ...range, from: e.target.value })}
              className="ml-2 rounded-ctl border border-line bg-surface-2 px-2 py-1 text-sm text-tx outline-none focus:border-brand"
            />
          </label>
          <label className="text-xs text-tx-3">
            To
            <input
              type="date"
              value={range.to}
              onChange={(e) => setRange({ ...range, to: e.target.value })}
              className="ml-2 rounded-ctl border border-line bg-surface-2 px-2 py-1 text-sm text-tx outline-none focus:border-brand"
            />
          </label>
          <button
            onClick={() => downloadRevenueCsv(params)}
            className="flex items-center gap-2 rounded-ctl bg-brand px-3 py-1.5 text-sm font-semibold text-bg hover:bg-brand-d"
          >
            <Download size={15} /> Export CSV
          </button>
        </div>
      </div>

      {/* KPI tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi icon={TrendingUp} label="MRR" value={egp(k.mrr)} hint={`ARR ${egp(k.arr)}`} />
        <Kpi icon={Users} label="Paying merchants" value={num(k.paying_merchants)} hint={`ARPU ${egp(k.arpu)}`} />
        <Kpi icon={Percent} label="Trial → paid" value={pct(k.trial_to_paid_conversion)} hint={`${num(k.active_trials)} active trials`} />
        <Kpi icon={ArrowDownRight} label="Logo churn" value={pct(k.logo_churn_rate)} hint={`Revenue churn ${pct(k.revenue_churn_rate)}`} />
        <Kpi icon={Repeat} label="Net revenue retention" value={pct(k.net_revenue_retention)} hint="vs prior equal period" />
        <Kpi icon={TrendingUp} label="LTV (est.)" value={egp(k.ltv)} hint="ARPU ÷ logo churn" />
        <Kpi icon={Gift} label="Comped merchants" value={num(k.comped_merchants)} hint="free access" />
      </div>

      {/* MRR movement / collected revenue over time */}
      <ChartCard title="Collected revenue by month">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data.monthly_series}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="month" stroke={COLORS.axis} fontSize={12} />
            <YAxis stroke={COLORS.axis} fontSize={12} />
            <Tooltip {...tooltipStyle} formatter={(v, name) => (name === 'collected_egp' ? egp(v) : num(v))} />
            <Bar dataKey="collected_egp" name="Collected (EGP)" fill={COLORS.brand} radius={[4, 4, 0, 0]} />
            <Bar dataKey="new_payers" name="New payers" fill={COLORS.info} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Revenue by plan */}
        <ChartCard title="MRR by plan">
          <div className="overflow-hidden rounded-ctl border border-line">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-tx-3">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">Plan</th>
                  <th className="px-3 py-2 font-medium text-right">Merchants</th>
                  <th className="px-3 py-2 font-medium text-right">MRR</th>
                </tr>
              </thead>
              <tbody>
                {data.revenue_by_plan.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-tx-3">
                      No paying merchants yet.
                    </td>
                  </tr>
                ) : (
                  data.revenue_by_plan.map((r) => (
                    <tr key={r.plan} className="border-b border-line/60 last:border-0">
                      <td className="px-3 py-2 text-tx">{r.plan}</td>
                      <td className="px-3 py-2 text-right font-num text-tx-2">{num(r.paying_merchants)}</td>
                      <td className="px-3 py-2 text-right font-num text-tx">{egp(r.mrr)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </ChartCard>

        {/* Cohort retention */}
        <ChartCard title="Cohort retention (by signup month)">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data.cohort_retention}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="cohort_month" stroke={COLORS.axis} fontSize={12} />
              <YAxis
                stroke={COLORS.axis}
                fontSize={12}
                domain={[0, 1]}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
              />
              <Tooltip {...tooltipStyle} formatter={(v) => pct(v)} />
              <Line
                type="monotone"
                dataKey="retention_pct"
                name="Still paying"
                stroke={COLORS.success}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
