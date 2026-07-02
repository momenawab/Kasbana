import { Link, Outlet, Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import UpgradeDrawer from '../components/UpgradeDrawer'
import AnnouncementBanner from '../components/AnnouncementBanner'
import { useAuth } from '../hooks/useAuth'
import { areaForPath, canAccess, landingFor } from '../lib/roles'
import { arDigits, daysUntil } from '../lib/format'
import { endImpersonation, isImpersonating } from '../lib/auth'

export default function Shell() {
  const { t, i18n } = useTranslation()
  const { merchant, role, impersonation } = useAuth()
  const location = useLocation()
  const lang = i18n.language

  // Role guard: once the role is known, bounce a user away from an area they
  // can't access (e.g. a Scanner typing /billing → their landing screen).
  const area = areaForPath(location.pathname)
  if (role && !canAccess(role, area)) {
    return <Navigate to={landingFor(role)} replace />
  }

  const status = merchant?.status
  const trialing = status === 'trial'
  const daysLeft = trialing && merchant?.trial_ends_at ? daysUntil(merchant.trial_ends_at) : 0
  // Soft-lock: trial elapsed but still on the trial plan (data visible, actions disabled).
  const softLocked = trialing && merchant?.trial_ends_at && daysLeft <= 0

  // Hard-lock: an admin suspended this merchant (Phase 9). The API already 403s
  // every action; show a clear full-screen state so staff aren't left guessing.
  if (status === 'suspended') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-paper p-6 text-center">
        <h1 className="font-head text-2xl font-bold text-ink">{t('suspended.title')}</h1>
        <p className="max-w-md text-tx-2">{t('suspended.body')}</p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Topbar />

        {/* Platform announcement banner (Phase 10) — most recent unread. */}
        <AnnouncementBanner />

        {/* Persistent impersonation banner (Phase 6) — an admin is viewing as
            this merchant; Exit discards the session token and closes the tab. */}
        {isImpersonating() && (
          <div className="flex items-center justify-between gap-3 bg-red-700 px-4 py-2 text-sm text-white">
            <span>
              {t('impersonation.banner', {
                merchant: merchant?.name || '…',
                admin: impersonation?.admin_email || 'support',
              })}
            </span>
            <button
              onClick={() => {
                endImpersonation()
                window.close()
                window.location.assign('/login')
              }}
              className="rounded-ctl bg-white px-3 py-1 font-semibold text-red-700"
            >
              {t('impersonation.exit')}
            </button>
          </div>
        )}

        {trialing && !softLocked && (
          <div className="flex items-center justify-between gap-3 bg-ink px-4 py-2 text-sm text-white">
            <span>{t('trial.banner', { count: arDigits(daysLeft, lang) })}</span>
            <Link to="/billing" className="rounded-ctl bg-amber px-3 py-1 text-ink font-semibold">
              {t('trial.cta')}
            </Link>
          </div>
        )}

        <main className="relative flex-1 p-4 pb-20 md:pb-4">
          <Outlet />

          {softLocked && (
            <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 bg-paper/80 backdrop-blur-sm">
              <p className="text-tx-2">{t('trial.expired')}</p>
              <Link to="/billing" className="rounded-ctl bg-amber px-4 py-2 text-ink font-semibold">
                {t('trial.expiredCta')}
              </Link>
            </div>
          )}
        </main>
      </div>

      {/* Global gating drawer — opened by usePlan guards or a server PLAN_LIMIT. */}
      <UpgradeDrawer />
    </div>
  )
}
