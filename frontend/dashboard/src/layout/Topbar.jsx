import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Globe, LogOut } from 'lucide-react'
import { setLang } from '../lib/i18n'
import { useAuth } from '../hooks/useAuth'
import { arDigits, daysUntil } from '../lib/format'

export default function Topbar() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { merchant, logout } = useAuth()
  const lang = i18n.language

  const toggleLang = () => setLang(lang === 'ar' ? 'en' : 'ar')
  const trialing = merchant?.status === 'trial'
  const daysLeft = trialing && merchant?.trial_ends_at ? daysUntil(merchant.trial_ends_at) : 0

  return (
    <header className="flex items-center justify-between border-b border-line bg-white px-4 py-3">
      <div className="font-head font-semibold text-slate">{merchant?.name || t('app.name')}</div>

      <div className="flex items-center gap-3">
        {trialing && (
          <button
            onClick={() => navigate('/billing')}
            className="rounded-full bg-violet-bg text-violet-d px-3 py-1 text-xs font-semibold font-num"
          >
            {t('trial.chip', { count: arDigits(daysLeft, lang) })}
          </button>
        )}
        <button
          onClick={toggleLang}
          className="flex items-center gap-1 rounded-ctl border border-line px-2 py-1 text-sm text-tx-2 hover:bg-paper"
          aria-label={t('common.language')}
        >
          <Globe size={16} />
          <span>{t('common.language')}</span>
        </button>
        <button
          onClick={logout}
          className="flex items-center gap-1 rounded-ctl px-2 py-1 text-sm text-tx-2 hover:bg-paper"
          aria-label={t('common.logout')}
        >
          <LogOut size={16} />
          <span className="hidden sm:inline">{t('common.logout')}</span>
        </button>
      </div>
    </header>
  )
}
