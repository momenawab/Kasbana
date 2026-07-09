import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  ScanLine,
  CreditCard,
  Users,
  BarChart3,
  MessageSquare,
  MapPin,
  UserCog,
  Receipt,
  Settings,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { canAccess } from '../lib/roles'

// `area` gates each item by role (null = open to all). The first 5 *visible*
// items also form the mobile bottom nav.
const NAV = [
  { to: '/', key: 'overview', Icon: LayoutDashboard, end: true, area: 'insights' },
  { to: '/scan', key: 'scan', Icon: ScanLine, area: 'scan' },
  { to: '/cards', key: 'cards', Icon: CreditCard, area: 'cards' },
  { to: '/customers', key: 'customers', Icon: Users, area: 'engage' },
  { to: '/analytics', key: 'analytics', Icon: BarChart3, area: 'insights' },
  { to: '/campaigns', key: 'messaging', Icon: MessageSquare, area: 'engage' },
  { to: '/locations', key: 'locations', Icon: MapPin, area: 'locations' },
  { to: '/team', key: 'team', Icon: UserCog, area: 'team' },
  { to: '/billing', key: 'billing', Icon: Receipt, area: 'billing' },
  { to: '/settings', key: 'settings', Icon: Settings, area: null },
]

function itemClass({ isActive }) {
  return (
    'flex items-center gap-3 rounded-ctl px-3 py-2 text-sm transition ' +
    (isActive ? 'bg-violet text-white font-semibold' : 'text-white/70 hover:text-white hover:bg-slate-2')
  )
}

export default function Sidebar() {
  const { t } = useTranslation()
  const { role } = useAuth()
  const items = NAV.filter((item) => canAccess(role, item.area))

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col bg-slate text-white p-4 gap-1">
        <div className="flex items-center gap-2 px-3 py-4">
          <img src="/logo.svg" alt="" className="h-7 w-7" />
          <span className="font-head text-xl font-bold text-white">{t('app.name')}</span>
        </div>
        <nav className="flex flex-col gap-1">
          {items.map(({ to, key, Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={itemClass}>
              <Icon size={18} />
              <span>{t(`nav.${key}`)}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile bottom nav (first 5 visible) */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-slate text-white flex justify-around py-2">
        {items.slice(0, 5).map(({ to, key, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              'flex flex-col items-center gap-1 px-2 text-[11px] ' +
              (isActive ? 'text-violet' : 'text-white/70')
            }
          >
            <Icon size={20} />
            <span>{t(`nav.${key}`)}</span>
          </NavLink>
        ))}
      </nav>
    </>
  )
}
