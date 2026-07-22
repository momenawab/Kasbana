import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Loader2 } from 'lucide-react'
import { useDashboard } from './api'

const AXIS = '#8b87a0'
const GRID = '#332F45'
const BRAND = '#845AEA'
const TOOLTIP = {
  background: '#262238',
  border: 'none',
  borderRadius: 10,
  fontSize: 12,
  color: '#fff',
}

// Warm→cool, so the chart reads the same way the labels do.
const LABEL_COLORS = { hot: '#F0546A', warm: '#F0A24B', cold: '#4B9CF0', ignore: '#4a4560' }

export default function Dashboard() {
  const [days, setDays] = useState(30)
  const { data, isLoading } = useDashboard(days)

  if (isLoading || !data) {
    return (
      <div className="flex justify-center py-20 text-tx-2">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  const m = data.metrics
  const presence = data.web_presence

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-tx">Overview</h2>
        <div className="flex gap-2">
          {[7, 30, 90].map((value) => (
            <button
              key={value}
              onClick={() => setDays(value)}
              className={
                'rounded-full px-3 py-1 text-xs font-semibold transition ' +
                (days === value
                  ? 'bg-brand text-white'
                  : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
              }
            >
              {value}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <Card label="Total leads" value={m.total_leads} />
        <Card label="New today" value={m.new_today} />
        <Card label="Hot" value={m.hot_leads} tone="text-danger" />
        <Card label="Ready" value={m.ready} tone="text-success" />
        <Card label="Imported" value={m.imported} tone="text-brand" />
        <Card label="Avg score" value={m.average_score} />
        <Card label="Verified" value={m.verified} hint="provider-confirmed" />
        <Card label="Pending" value={m.pending} />
        <Card label="Rejected" value={m.rejected} />
        <Card label="Jobs running" value={m.jobs_running} />
        <Card label="Jobs failed" value={m.jobs_failed} tone={m.jobs_failed ? 'text-danger' : ''} />
        <Card
          label="Est. spend"
          value={`$${Number(m.estimated_cost_usd).toFixed(2)}`}
          hint={`${m.estimated_api_calls} calls · ${m.estimated_tokens.toLocaleString()} tokens`}
        />
      </div>

      {/* The number that forced the scoring rebalance. Anyone retuning weights
          needs to see the market's shape before they start. */}
      <Panel title="Web presence" subtitle="Most of this market has no site of its own">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Mini label="Own website" value={presence.with_website} total={presence.total} />
          <Mini label="Social only" value={presence.with_social_only} total={presence.total} />
          <Mini label="Nothing online" value={presence.with_nothing} total={presence.total} />
          <Mini label="Owner named" value={presence.with_owner_name} total={presence.total} />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Leads per day">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data.leads_per_day}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="day" stroke={AXIS} fontSize={11} />
              <YAxis stroke={AXIS} fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP} />
              <Line type="monotone" dataKey="count" stroke={BRAND} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Score distribution" subtitle="Ten-point bands">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.score_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="band" stroke={AXIS} fontSize={10} />
              <YAxis stroke={AXIS} fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="count" fill={BRAND} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Leads by city">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.leads_by_city} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={11} allowDecimals={false} />
              <YAxis dataKey="city" type="category" stroke={AXIS} fontSize={11} width={90} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="count" fill={BRAND} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="By band">
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={data.by_label}
                dataKey="count"
                nameKey="label_display"
                innerRadius={45}
                outerRadius={75}
                paddingAngle={2}
              >
                {data.by_label.map((row) => (
                  <Cell key={row.label} fill={LABEL_COLORS[row.label] || '#4a4560'} />
                ))}
              </Pie>
              <Tooltip contentStyle={TOOLTIP} />
            </PieChart>
          </ResponsiveContainer>
          <Legend rows={data.by_label} colors={LABEL_COLORS} labelKey="label" />
        </Panel>

        <Panel
          title="Owner name sources"
          subtitle="Discovery source is always Google Places — this is the one that varies"
        >
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.owner_sources} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={11} allowDecimals={false} />
              <YAxis
                dataKey="source_display"
                type="category"
                stroke={AXIS}
                fontSize={10}
                width={130}
              />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="count" fill={BRAND} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Business categories">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.by_category}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="category_display" stroke={AXIS} fontSize={10} />
              <YAxis stroke={AXIS} fontSize={11} allowDecimals={false} />
              <Tooltip contentStyle={TOOLTIP} />
              <Bar dataKey="count" fill={BRAND} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title="Conversion"
        subtitle="Whether prospecting pays — through to merchants, not just CRM records"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Step label="Discovered" value={data.conversion.discovered} />
          <Arrow rate={data.conversion.ready_rate} />
          <Step label="Ready" value={data.conversion.ready} />
          <Arrow rate={data.conversion.import_rate} />
          <Step label="Imported" value={data.conversion.imported} />
          <Arrow rate={data.conversion.conversion_rate} />
          <Step label="Merchants" value={data.conversion.converted} tone="text-success" />
        </div>
      </Panel>
    </div>
  )
}

function Card({ label, value, hint, tone = 'text-tx' }) {
  return (
    <div className="rounded-card bg-surface p-3">
      <p className={`text-xl font-semibold ${tone}`}>{value}</p>
      <p className="text-xs text-tx-2">{label}</p>
      {hint && <p className="mt-0.5 text-[11px] text-tx-2/70">{hint}</p>}
    </div>
  )
}

function Mini({ label, value, total }) {
  const pct = total ? Math.round((value / total) * 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-tx-2">{label}</span>
        <span className="text-tx">
          {value} <span className="text-tx-2">({pct}%)</span>
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
        <div className="h-full bg-brand" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function Panel({ title, subtitle, children }) {
  return (
    <div className="rounded-card bg-surface p-4">
      <h3 className="text-sm font-semibold text-tx">{title}</h3>
      {subtitle && <p className="mb-2 mt-0.5 text-xs text-tx-2">{subtitle}</p>}
      <div className="mt-2">{children}</div>
    </div>
  )
}

function Legend({ rows, colors, labelKey }) {
  return (
    <div className="mt-2 flex flex-wrap justify-center gap-3">
      {rows.map((row) => (
        <span key={row[labelKey]} className="flex items-center gap-1.5 text-xs text-tx-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: colors[row[labelKey]] || '#4a4560' }}
          />
          {row.label_display} {row.count}
        </span>
      ))}
    </div>
  )
}

function Step({ label, value, tone = 'text-tx' }) {
  return (
    <div className="rounded-ctl bg-surface-2 px-4 py-2 text-center">
      <p className={`text-lg font-semibold ${tone}`}>{value}</p>
      <p className="text-xs text-tx-2">{label}</p>
    </div>
  )
}

function Arrow({ rate }) {
  return (
    <div className="text-center text-xs text-tx-2">
      <div>→</div>
      <div>{rate}%</div>
    </div>
  )
}
