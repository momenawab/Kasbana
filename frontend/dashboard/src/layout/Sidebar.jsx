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

// Nav is grouped into labelled sections for scannability. `area` gates each
// item by role (null = open to all). `section` is null for the top item (no
// header). The mobile bottom bar flattens the first 5 *visible* items.
const NAV = [
  { to: '/', key: 'overview', Icon: LayoutDashboard, end: true, area: 'insights', section: null },
  { to: '/scan', key: 'scan', Icon: ScanLine, area: 'scan', section: 'operate' },
  { to: '/cards', key: 'cards', Icon: CreditCard, area: 'cards', section: 'operate' },
  { to: '/customers', key: 'customers', Icon: Users, area: 'engage', section: 'operate' },
  { to: '/campaigns', key: 'messaging', Icon: MessageSquare, area: 'engage', section: 'grow' },
  { to: '/analytics', key: 'analytics', Icon: BarChart3, area: 'insights', section: 'grow' },
  { to: '/locations', key: 'locations', Icon: MapPin, area: 'locations', section: 'business' },
  { to: '/team', key: 'team', Icon: UserCog, area: 'team', section: 'business' },
  { to: '/billing', key: 'billing', Icon: Receipt, area: 'billing', section: 'business' },
  { to: '/settings', key: 'settings', Icon: Settings, area: null, section: 'general' },
]

function itemClass({ isActive }) {
  return (
    'group relative flex items-center gap-3 rounded-ctl px-3 py-2 text-sm transition ' +
    (isActive
      ? 'bg-violet text-white font-semibold shadow-pop'
      : 'text-tx-2 hover:bg-surface-2 hover:text-tx')
  )
}

export default function Sidebar() {
  const { t } = useTranslation()
  const { role } = useAuth()
  const items = NAV.filter((item) => canAccess(role, item.area))

  // Group consecutive items by their section for rendering headers.
  const groups = []
  for (const item of items) {
    const last = groups[groups.length - 1]
    if (last && last.section === item.section) last.items.push(item)
    else groups.push({ section: item.section, items: [item] })
  }

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="theme-t hidden md:flex md:w-64 md:flex-col border-e border-line bg-surface p-3">
        <div className="flex items-center gap-2.5 px-2 py-4">
          <img src="/logo.svg" alt="" className="h-8 w-8" />
          <span className="font-head text-xl font-bold text-tx">{t('app.name')}</span>
        </div>
        <nav className="mt-2 flex flex-1 flex-col gap-1">
          {groups.map((group, gi) => (
            <div key={gi} className={gi > 0 ? 'mt-4' : ''}>
              {group.section && (
                <div className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-tx-3">
                  {t(`navSection.${group.section}`)}
                </div>
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map(({ to, key, Icon, end }) => (
                  <NavLink key={to} to={to} end={end} className={itemClass}>
                    <Icon size={18} className="shrink-0" />
                    <span>{t(`nav.${key}`)}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      {/* Mobile bottom nav (first 5 visible) */}
      <nav className="theme-t md:hidden fixed bottom-0 inset-x-0 z-40 border-t border-line bg-surface flex justify-around py-2">
        {items.slice(0, 5).map(({ to, key, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              'flex flex-col items-center gap-1 px-2 text-[11px] transition ' +
              (isActive ? 'text-violet font-semibold' : 'text-tx-3')
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
