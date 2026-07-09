// Recharts wrappers in Direction-C token colors (spec §10).
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
const LINE = '#E9E6F2'
const AXIS = '#8B8798'

// Line/area chart — violet line + area gradient.
export function ChartLine({ data, xKey = 'date', yKey = 'value', height = 240, color = VIOLET }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id="kc-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: AXIS }} />
        <Tooltip />
        <Area type="monotone" dataKey={yKey} stroke={color} strokeWidth={2} fill="url(#kc-area)" />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ChartBar({ data, xKey = 'date', yKey = 'value', height = 240, color = TEAL }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={LINE} />
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} />
        <YAxis tick={{ fontSize: 11, fill: AXIS }} />
        <Tooltip />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
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
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}
