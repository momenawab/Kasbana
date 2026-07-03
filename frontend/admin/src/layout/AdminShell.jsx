import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  Building2,
  CreditCard,
  Receipt,
  LifeBuoy,
  BarChart3,
  PieChart,
  Workflow,
  Megaphone,
  Ticket,
  Users2,
  ScrollText,
  ShieldAlert,
  Activity,
  Lock,
  LogOut,
  Loader2,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

// Full nav — later phases enable each destination. Phase 1 ships the shell +
// Overview; the rest are placeholders so the map of the console is visible.
const NAV = [
  { to: '/', key: 'Overview', Icon: LayoutDashboard, end: true, ready: true },
  { to: '/merchants', key: 'Merchants', Icon: Building2, ready: true },
  { to: '/plans', key: 'Plans', Icon: CreditCard, ready: true },
  { to: '/billing', key: 'Billing', Icon: Receipt, ready: true },
  { to: '/support', key: 'Support', Icon: LifeBuoy, phase: 6 },
  { to: '/revenue', key: 'Revenue', Icon: BarChart3, ready: true, financeOnly: true },
  { to: '/platform', key: 'Platform', Icon: PieChart, ready: true },
  { to: '/lifecycle', key: 'Lifecycle', Icon: Workflow, ready: true },
  { to: '/announcements', key: 'Announcements', Icon: Megaphone, ready: true },
  { to: '/promotions', key: 'Promotions', Icon: Ticket, ready: true },
  { to: '/team', key: 'Admin Team', Icon: Users2, ready: true },
  { to: '/audit', key: 'Audit Log', Icon: ScrollText, ready: true },
  { to: '/compliance', key: 'Compliance', Icon: ShieldAlert, ready: true },
  { to: '/ops', key: 'Operations', Icon: Activity, ready: true },
  { to: '/security', key: 'Security', Icon: Lock, ready: true },
]

function itemClass({ isActive }) {
  return (
    'flex items-center gap-3 rounded-ctl px-3 py-2 text-sm transition ' +
    (isActive ? 'bg-brand text-bg font-semibold' : 'text-tx-2 hover:bg-surface-2 hover:text-tx')
  )
}

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

export default function AdminShell() {
  const { admin, role, isLoading, logout } = useAuth()

  // Financials are Finance/Super-admin only — hide the Revenue nav for everyone
  // else (the route itself also guards, so a direct URL still won't leak data).
  const nav = NAV.filter((item) => !item.financeOnly || FINANCE_ROLES.includes(role))

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Sidebar */}
      <aside className="hidden w-60 flex-col border-r border-line bg-surface p-4 md:flex">
        <div className="px-2 py-3 font-head text-lg font-bold text-tx">
          Stampn <span className="text-brand">Admin</span>
        </div>
        <nav className="mt-2 flex flex-1 flex-col gap-1">
          {nav.map(({ to, key, Icon, end, ready }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={itemClass}
              onClick={(e) => {
                if (!ready) e.preventDefault() // placeholder until its phase ships
              }}
            >
              <Icon size={18} />
              <span className="flex-1">{key}</span>
              {!ready && <span className="text-[10px] text-tx-3">soon</span>}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={logout}
          className="mt-2 flex items-center gap-3 rounded-ctl px-3 py-2 text-sm text-tx-2 hover:bg-surface-2 hover:text-tx"
        >
          <LogOut size={18} />
          Sign out
        </button>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
          <span className="text-sm text-tx-3">Platform operations</span>
          <div className="flex items-center gap-3 text-sm">
            {isLoading ? (
              <Loader2 size={16} className="animate-spin text-tx-3" />
            ) : (
              <>
                <span className="text-tx-2">{admin?.email}</span>
                <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-brand">
                  {admin?.role}
                </span>
              </>
            )}
          </div>
        </header>
        <main className="flex-1 p-5">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
