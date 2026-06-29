import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  CreditCard,
  Users,
  BarChart3,
  MessageSquare,
  MapPin,
  UserCog,
  Receipt,
  Settings,
} from 'lucide-react'

// Order matters: first 5 also form the mobile bottom nav.
const NAV = [
  { to: '/', key: 'overview', Icon: LayoutDashboard, end: true },
  { to: '/cards', key: 'cards', Icon: CreditCard },
  { to: '/customers', key: 'customers', Icon: Users },
  { to: '/analytics', key: 'analytics', Icon: BarChart3 },
  { to: '/campaigns', key: 'messaging', Icon: MessageSquare },
  { to: '/locations', key: 'locations', Icon: MapPin },
  { to: '/team', key: 'team', Icon: UserCog },
  { to: '/billing', key: 'billing', Icon: Receipt },
  { to: '/settings', key: 'settings', Icon: Settings },
]

function itemClass({ isActive }) {
  return (
    'flex items-center gap-3 rounded-ctl px-3 py-2 text-sm transition ' +
    (isActive ? 'bg-amber text-ink font-semibold' : 'text-white/70 hover:text-white hover:bg-ink-2')
  )
}

export default function Sidebar() {
  const { t } = useTranslation()
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-60 md:flex-col bg-ink text-white p-4 gap-1">
        <div className="px-3 py-4 font-head text-xl font-bold text-white">{t('app.name')}</div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, key, Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={itemClass}>
              <Icon size={18} />
              <span>{t(`nav.${key}`)}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile bottom nav (first 5) */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-ink text-white flex justify-around py-2">
        {NAV.slice(0, 5).map(({ to, key, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              'flex flex-col items-center gap-1 px-2 text-[11px] ' +
              (isActive ? 'text-amber' : 'text-white/70')
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
