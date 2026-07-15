// Recharts wrappers in Direction-C token colors (spec §10).
import { useId } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Brand chart palette — matches the Stampn logo tokens (see tailwind.config.js).
const VIOLET = '#845AEA'
const SLATE = '#1E1B2E'
const TEAL = '#1C7C73'
const FUCHSIA = '#D43DCF'
// Neutral translucent grid + axis so charts read on light surfaces, dark
// surfaces, and the always-dark trend card alike.
const GRID = 'rgba(148,143,163,0.22)'
const AXIS = '#8B8798'

// Recharts' default tooltip paints a white card but leaves the label to inherit
// the page text colour — which is near-white under .dark, so the hovered date
// read white-on-white. Pin the card and the label to fixed values so the tooltip
// stays legible in both themes.
const TOOLTIP_CARD = {
  background: '#FFFFFF',
  border: '1px solid rgba(148,143,163,0.35)',
  borderRadius: 10,
  boxShadow: '0 6px 20px rgba(30,27,46,0.18)',
  padding: '8px 10px',
}
const TOOLTIP_LABEL = { color: SLATE, fontWeight: 600, marginBottom: 2 }
const TOOLTIP_ITEM = { color: SLATE }

// Spread onto a <Tooltip>, never wrapped in a component: recharts discovers
// Tooltip/Legend/axes by scanning its children for those exact element types, so a
// custom wrapper component makes the chart ignore the tooltip entirely.
const TOOLTIP_PROPS = {
  contentStyle: TOOLTIP_CARD,
  labelStyle: TOOLTIP_LABEL,
  itemStyle: TOOLTIP_ITEM,
  cursor: { fill: 'rgba(148,143,163,0.12)' },
}

// Line/area chart — violet line + area gradient.
export function ChartLine({
  data,
  xKey = 'date',
  yKey = 'value',
  height = 240,
  color = VIOLET,
  name,
  labelFormatter,
  tickFormatter,
}) {
  // The gradient is referenced by DOM id, so it has to be unique per instance —
  // the expanded chart renders alongside the small one it was opened from. The
  // colons React puts in useId() are unreliable inside an SVG url(#…), so drop them.
  const gradientId = `kc-area-${useId().replace(/:/g, '')}`
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} tickFormatter={tickFormatter} />
        <YAxis tick={{ fontSize: 11, fill: AXIS }} allowDecimals={false} />
        <Tooltip {...TOOLTIP_PROPS} labelFormatter={labelFormatter} />
        <Area
          type="monotone"
          dataKey={yKey}
          name={name}
          stroke={color}
          strokeWidth={2}
          fill={`url(#${gradientId})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ChartBar({
  data,
  xKey = 'date',
  yKey = 'value',
  height = 240,
  color = TEAL,
  name,
  labelFormatter,
  tickFormatter,
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} tickFormatter={tickFormatter} />
        <YAxis tick={{ fontSize: 11, fill: AXIS }} allowDecimals={false} />
        <Tooltip {...TOOLTIP_PROPS} labelFormatter={labelFormatter} />
        <Bar dataKey={yKey} name={name} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ChartDonut({ data, height = 240 }) {
  const colors = [VIOLET, FUCHSIA, TEAL, SLATE]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="80%">
          {data.map((_, i) => (
            <Cell key={i} fill={colors[i % colors.length]} />
          ))}
        </Pie>
        <Legend />
        <Tooltip {...TOOLTIP_PROPS} />
      </PieChart>
    </ResponsiveContainer>
  )
}
