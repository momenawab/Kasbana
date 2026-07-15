import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  UserPlus,
  MessageSquare,
  Building2,
  CreditCard,
  Receipt,
  LifeBuoy,
  BarChart3,
  PieChart,
  Workflow,
  Megaphone,
  Ticket,
  Handshake,
  Users2,
  ScrollText,
  ShieldAlert,
  Activity,
  Lock,
  LogOut,
  Loader2,
  Menu,
  X,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

// Full nav — later phases enable each destination. Phase 1 ships the shell +
// Overview; the rest are placeholders so the map of the console is visible.
const NAV = [
  { to: '/', key: 'Overview', Icon: LayoutDashboard, end: true, ready: true },
  { to: '/leads', key: 'Leads', Icon: UserPlus, ready: true },
  { to: '/messages', key: 'Messages', Icon: MessageSquare, ready: true },
  { to: '/merchants', key: 'Merchants', Icon: Building2, ready: true },
  { to: '/plans', key: 'Plans', Icon: CreditCard, ready: true },
  { to: '/billing', key: 'Billing', Icon: Receipt, ready: true },
  { to: '/support', key: 'Support', Icon: LifeBuoy, phase: 6 },
  { to: '/revenue', key: 'Revenue', Icon: BarChart3, ready: true, financeOnly: true },
  { to: '/platform', key: 'Platform', Icon: PieChart, ready: true },
  { to: '/lifecycle', key: 'Lifecycle', Icon: Workflow, ready: true },
  { to: '/announcements', key: 'Announcements', Icon: Megaphone, ready: true },
  { to: '/promotions', key: 'Promotions', Icon: Ticket, ready: true },
  { to: '/partners', key: 'Partners', Icon: Handshake, ready: true },
  { to: '/team', key: 'Admin Team', Icon: Users2, ready: true },
  { to: '/audit', key: 'Audit Log', Icon: ScrollText, ready: true },
  { to: '/compliance', key: 'Compliance', Icon: ShieldAlert, ready: true },
  { to: '/ops', key: 'Operations', Icon: Activity, ready: true },
  { to: '/security', key: 'Security', Icon: Lock, ready: true },
]

function itemClass({ isActive }) {
  return (
    'flex items-center gap-3 rounded-ctl px-3 py-2 text-sm transition ' +
    (isActive ? 'bg-brand text-white font-semibold' : 'text-tx-2 hover:bg-surface-2 hover:text-tx')
  )
}

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

function Brand() {
  return (
    <div className="flex items-center gap-2 px-2 py-3">
      <img src="/logo.png" alt="" className="h-8 w-8 rounded-full" />
      <span className="font-head text-lg font-bold text-tx">
        Stampn <span className="text-brand">Admin</span>
      </span>
    </div>
  )
}

// Shared nav list — rendered in both the desktop sidebar and the mobile drawer.
function NavList({ nav, onNavigate }) {
  return (
    <nav className="mt-2 flex flex-1 flex-col gap-1 overflow-y-auto">
      {nav.map(({ to, key, Icon, end, ready }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={itemClass}
          onClick={(e) => {
            if (!ready)
              e.preventDefault() // placeholder until its phase ships
            else onNavigate?.()
          }}
        >
          <Icon size={18} />
          <span className="flex-1">{key}</span>
          {!ready && <span className="text-[10px] text-tx-3">soon</span>}
        </NavLink>
      ))}
    </nav>
  )
}

function SignOut({ logout }) {
  return (
    <button
      onClick={logout}
      className="mt-2 flex items-center gap-3 rounded-ctl px-3 py-2 text-sm text-tx-2 hover:bg-surface-2 hover:text-tx"
    >
      <LogOut size={18} />
      Sign out
    </button>
  )
}

export default function AdminShell() {
  const { admin, role, isLoading, logout } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Financials are Finance/Super-admin only — hide the Revenue nav for everyone
  // else (the route itself also guards, so a direct URL still won't leak data).
  const nav = NAV.filter((item) => !item.financeOnly || FINANCE_ROLES.includes(role))

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 flex-col border-r border-line bg-surface p-4 md:flex">
        <Brand />
        <NavList nav={nav} />
        <SignOut logout={logout} />
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 flex w-64 max-w-[82%] flex-col border-r border-line bg-surface p-4 shadow-pop">
            <div className="flex items-center justify-between">
              <Brand />
              <button
                onClick={() => setDrawerOpen(false)}
                aria-label="Close menu"
                className="rounded-ctl p-2 text-tx-2 hover:bg-surface-2 hover:text-tx"
              >
                <X size={20} />
              </button>
            </div>
            <NavList nav={nav} onNavigate={() => setDrawerOpen(false)} />
            <SignOut logout={logout} />
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Desktop header */}
        <header className="hidden items-center justify-between border-b border-line bg-surface px-5 py-3 md:flex">
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

        {/* Mobile top bar */}
        <header className="flex items-center justify-between gap-2 border-b border-line bg-surface px-4 py-3 md:hidden">
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="rounded-ctl p-2 text-tx-2 hover:bg-surface-2 hover:text-tx"
          >
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="" className="h-7 w-7 rounded-full" />
            <span className="font-head text-base font-bold text-tx">
              Stampn <span className="text-brand">Admin</span>
            </span>
          </div>
          {admin?.role ? (
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs text-brand">
              {admin.role}
            </span>
          ) : (
            <span className="w-8" />
          )}
        </header>

        <main className="min-w-0 flex-1 p-4 sm:p-5">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
