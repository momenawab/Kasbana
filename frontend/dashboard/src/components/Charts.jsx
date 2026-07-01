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

const AMBER = '#E0A23B'
const INK = '#0E1B2A'
const TEAL = '#1C7C73'
const CLAY = '#C75D43'
const LINE = '#E7E1D6'

// Line/area chart — dark Direction-C card uses amber line + area gradient.
export function ChartLine({ data, xKey = 'date', yKey = 'value', height = 240, color = AMBER }) {
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
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: '#8A949C' }} />
        <YAxis tick={{ fontSize: 11, fill: '#8A949C' }} />
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
        <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: '#8A949C' }} />
        <YAxis tick={{ fontSize: 11, fill: '#8A949C' }} />
        <Tooltip />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ChartDonut({ data, height = 240 }) {
  const colors = [INK, AMBER, TEAL, CLAY]
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
