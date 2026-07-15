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
  ArrowRight,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { useAuth } from '../../hooks/useAuth'
import { usePlatformAnalytics } from '../platform/api'
import { num } from '../../lib/format'

const COLORS = { brand: '#845AEA', grid: '#2F2A42', axis: '#7C7891' }
const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

const tooltipStyle = {
  contentStyle: {
    background: '#262238',
    border: '1px solid #2F2A42',
    borderRadius: 9,
    color: '#EDEBF5',
  },
  labelStyle: { color: '#A9A3BE' },
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

function Card({ title, action, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-head text-sm font-semibold text-tx">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  )
}

export default function Home() {
  const { admin, role } = useAuth()
  const { data, isLoading, isError } = usePlatformAnalytics()
  const isFinance = FINANCE_ROLES.includes(role)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-head text-2xl font-bold text-tx">
            Welcome{admin?.name ? `, ${admin.name}` : ''}
          </h1>
          <p className="mt-1 text-sm text-tx-2">Your platform at a glance.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link
            to="/platform"
            className="inline-flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-tx-2 hover:bg-surface-2 hover:text-tx"
          >
            Full analytics <ArrowRight size={15} />
          </Link>
          {isFinance && (
            <Link
              to="/revenue"
              className="inline-flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-tx-2 hover:bg-surface-2 hover:text-tx"
            >
              Revenue <ArrowRight size={15} />
            </Link>
          )}
        </div>
      </div>

      {isLoading ? (
        <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
      ) : isError || !data ? (
        <div className="text-sm text-danger">Couldn’t load platform analytics.</div>
      ) : (
        <Dashboard data={data} />
      )}
    </div>
  )
}

function Dashboard({ data }) {
  const { merchants: mc, totals, wallet, growth, top_merchants } = data
  const walletTotal = wallet.apple + wallet.google
  const applePct = walletTotal ? Math.round((wallet.apple / walletTotal) * 100) : 0
  const top = (top_merchants || []).slice(0, 5)

  return (
    <>
      {/* Merchant lifecycle */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Stat
          icon={Building2}
          label="Merchants"
          value={num(mc.total)}
          hint={`${num(mc.active)} active`}
        />
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

      {/* Growth chart */}
      <Card
        title="Merchant growth"
        action={
          <Link to="/platform" className="text-xs text-brand hover:underline">
            Details
          </Link>
        }
      >
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={growth}>
            <defs>
              <linearGradient id="home-g" x1="0" y1="0" x2="0" y2="1">
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
              fill="url(#home-g)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Wallet split */}
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

        {/* Top merchants */}
        <Card
          title="Top merchants"
          action={
            <Link to="/merchants" className="text-xs text-brand hover:underline">
              All merchants
            </Link>
          }
        >
          <div className="overflow-hidden rounded-ctl border border-line">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-tx-3">
                <tr className="text-left">
                  <th className="px-3 py-2 font-medium">Merchant</th>
                  <th className="px-3 py-2 text-right font-medium">Customers</th>
                  <th className="px-3 py-2 text-right font-medium">Activity</th>
                </tr>
              </thead>
              <tbody>
                {top.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="px-3 py-6 text-center text-tx-3">
                      No activity yet.
                    </td>
                  </tr>
                ) : (
                  top.map((m) => (
                    <tr key={m.id} className="border-b border-line/60 last:border-0">
                      <td className="px-3 py-2">
                        <Link to={`/merchants/${m.id}`} className="text-brand hover:underline">
                          {m.name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-right font-num text-tx-2">
                        {num(m.customers)}
                      </td>
                      <td className="px-3 py-2 text-right font-num text-tx">{num(m.activity)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  )
}
