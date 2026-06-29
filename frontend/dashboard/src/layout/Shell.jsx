import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useAuth } from '../hooks/useAuth'
import { arDigits, daysUntil } from '../lib/format'

export default function Shell() {
  const { t, i18n } = useTranslation()
  const { merchant } = useAuth()
  const lang = i18n.language

  const status = merchant?.status
  const trialing = status === 'trial'
  const daysLeft = trialing && merchant?.trial_ends_at ? daysUntil(merchant.trial_ends_at) : 0
  // Soft-lock: trial elapsed but still on the trial plan (data visible, actions disabled).
  const softLocked = trialing && merchant?.trial_ends_at && daysLeft <= 0

  return (
    <div className="flex min-h-screen bg-paper">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Topbar />

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
    </div>
  )
}
