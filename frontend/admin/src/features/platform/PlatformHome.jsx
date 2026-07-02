import { Link } from 'react-router-dom'
import {
  Loader2,
  Building2,
  Users,
  CreditCard,
  Stamp,
  Gift,
  Apple,
  Smartphone,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { usePlatformAnalytics } from './api'
import { num } from '../../lib/format'

const COLORS = { brand: '#E0A23B', info: '#3B9FE0', success: '#2FBF87', grid: '#2A3648', axis: '#6B7A8D' }

const FEATURE_LABELS = {
  referrals: 'Referrals',
  points: 'Points cards',
  automations: 'Automations',
  branded_enroll: 'Branded enroll',
  campaigns: 'Campaigns',
}

const FUNNEL_LABELS = {
  signed_up: 'Signed up',
  activated: 'Built a card',
  active_access: 'Active access',
  paying: 'Paying',
}

const tooltipStyle = {
  contentStyle: { background: '#1B2637', border: '1px solid #2A3648', borderRadius: 9, color: '#E6EAF0' },
  labelStyle: { color: '#9AA7B8' },
}

function Stat({ icon: Icon, label, value, hint }) {
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

function Card({ title, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <h2 className="mb-4 font-head text-sm font-semibold text-tx">{title}</h2>
      {children}
    </div>
  )
}

export default function PlatformHome() {
  const { data, isLoading, isError } = usePlatformAnalytics()

  if (isLoading) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
  if (isError || !data) return <div className="text-sm text-danger">Couldn’t load platform analytics.</div>

  const { merchants: mc, totals, wallet, feature_adoption, growth, funnel, top_merchants } = data
  const walletTotal = wallet.apple + wallet.google
  const applePct = walletTotal ? Math.round((wallet.apple / walletTotal) * 100) : 0
  const maxFunnel = Math.max(1, ...funnel.map((f) => f.count))

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Platform &amp; Usage</h1>

      {/* Merchant lifecycle */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Stat icon={Building2} label="Merchants" value={num(mc.total)} />
        <Stat icon={Building2} label="Active" value={num(mc.active)} />
        <Stat icon={Building2} label="Trialing" value={num(mc.trialing)} />
        <Stat icon={Building2} label="Past due" value={num(mc.past_due)} />
        <Stat icon={Building2} label="Churned" value={num(mc.churned)} />
        <Stat icon={Building2} label="Suspended" value={num(mc.suspended)} />
      </div>

      {/* Platform totals */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={Users} label="Customers" value={num(totals.customers)} />
        <Stat icon={CreditCard} label="Cards" value={num(totals.cards)} />
        <Stat icon={Stamp} label="Stamps issued" value={num(totals.stamps)} />
        <Stat icon={Gift} label="Redemptions" value={num(totals.redemptions)} />
      </div>

      {/* Growth */}
      <Card title="Merchant growth">
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={growth}>
            <defs>
              <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={COLORS.brand} stopOpacity={0.4} />
                <stop offset="95%" stopColor={COLORS.brand} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="month" stroke={COLORS.axis} fontSize={12} />
            <YAxis stroke={COLORS.axis} fontSize={12} />
            <Tooltip {...tooltipStyle} />
            <Area
              type="monotone"
              dataKey="cumulative"
              name="Total merchants"
              stroke={COLORS.brand}
              fill="url(#g)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Feature adoption */}
        <Card title="Feature adoption">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={feature_adoption.map((f) => ({ ...f, label: FEATURE_LABELS[f.key] || f.key }))}
              layout="vertical"
              margin={{ left: 24 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} horizontal={false} />
              <XAxis type="number" stroke={COLORS.axis} fontSize={12} />
              <YAxis type="category" dataKey="label" stroke={COLORS.axis} fontSize={12} width={90} />
              <Tooltip {...tooltipStyle} formatter={(v, n) => (n === 'merchants' ? num(v) : v)} />
              <Bar dataKey="merchants" name="merchants" fill={COLORS.info} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Wallet split + funnel */}
        <div className="flex flex-col gap-4">
          <Card title="Wallet passes">
            <div className="flex items-center justify-around">
              <div className="flex items-center gap-2">
                <Apple size={20} className="text-tx-2" />
                <span className="font-num text-2xl text-tx">{num(wallet.apple)}</span>
              </div>
              <div className="flex items-center gap-2">
                <Smartphone size={20} className="text-tx-2" />
                <span className="font-num text-2xl text-tx">{num(wallet.google)}</span>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full bg-brand" style={{ width: `${applePct}%` }} />
            </div>
            <div className="mt-1 flex justify-between text-xs text-tx-3">
              <span>Apple {applePct}%</span>
              <span>Google {100 - applePct}%</span>
            </div>
          </Card>

          <Card title="Acquisition funnel">
            <div className="flex flex-col gap-2">
              {funnel.map((f) => (
                <div key={f.stage}>
                  <div className="mb-1 flex justify-between text-xs text-tx-3">
                    <span>{FUNNEL_LABELS[f.stage] || f.stage}</span>
                    <span className="font-num text-tx-2">{num(f.count)}</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className="h-full bg-success"
                      style={{ width: `${Math.round((f.count / maxFunnel) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Activity leaderboard */}
      <Card title="Top merchants by activity">
        <div className="overflow-hidden rounded-ctl border border-line">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-3 py-2 font-medium">Merchant</th>
                <th className="px-3 py-2 font-medium text-right">Customers</th>
                <th className="px-3 py-2 font-medium text-right">Loyalty events</th>
              </tr>
            </thead>
            <tbody>
              {top_merchants.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-3 py-6 text-center text-tx-3">
                    No activity yet.
                  </td>
                </tr>
              ) : (
                top_merchants.map((m) => (
                  <tr key={m.id} className="border-b border-line/60 last:border-0">
                    <td className="px-3 py-2">
                      <Link to={`/merchants/${m.id}`} className="text-brand hover:underline">
                        {m.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right font-num text-tx-2">{num(m.customers)}</td>
                    <td className="px-3 py-2 text-right font-num text-tx">{num(m.activity)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
