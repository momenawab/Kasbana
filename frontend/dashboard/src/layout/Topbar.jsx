import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Globe, LogOut, Sun, Moon } from 'lucide-react'
import { setLang } from '../lib/i18n'
import { useTheme, toggleTheme } from '../lib/theme'
import { useAuth } from '../hooks/useAuth'
import { arDigits, daysUntil } from '../lib/format'

export default function Topbar() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { merchant, logout } = useAuth()
  const theme = useTheme()
  const lang = i18n.language

  const toggleLang = () => setLang(lang === 'ar' ? 'en' : 'ar')
  const trialing = merchant?.status === 'trial'
  const daysLeft = trialing && merchant?.trial_ends_at ? daysUntil(merchant.trial_ends_at) : 0
  const name = merchant?.name || t('app.name')
  const initial = name.trim().charAt(0).toUpperCase()
  const isDark = theme === 'dark'

  return (
    <header className="theme-t sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-surface/80 px-4 py-3 backdrop-blur-md">
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-ctl bg-violet/10 font-head text-sm font-bold text-violet-d">
          {initial}
        </span>
        <span className="truncate font-head font-semibold text-tx">{name}</span>
      </div>

      <div className="flex items-center gap-1.5">
        {trialing && (
          <button
            onClick={() => navigate('/billing')}
            className="hidden rounded-full bg-violet-bg px-3 py-1 text-xs font-semibold text-violet-d font-num sm:block"
          >
            {t('trial.chip', { count: arDigits(daysLeft, lang) })}
          </button>
        )}
        <button
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-ctl text-tx-2 transition hover:bg-surface-2 hover:text-tx"
          aria-label={isDark ? t('theme.toLight') : t('theme.toDark')}
          title={isDark ? t('theme.toLight') : t('theme.toDark')}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <button
          onClick={toggleLang}
          className="flex items-center gap-1.5 rounded-ctl px-2.5 py-1.5 text-sm text-tx-2 transition hover:bg-surface-2 hover:text-tx"
          aria-label={t('common.language')}
        >
          <Globe size={16} />
          <span className="hidden sm:inline">{t('common.language')}</span>
        </button>
        <button
          onClick={logout}
          className="flex items-center gap-1.5 rounded-ctl px-2.5 py-1.5 text-sm text-tx-2 transition hover:bg-surface-2 hover:text-tx"
          aria-label={t('common.logout')}
        >
          <LogOut size={16} />
          <span className="hidden md:inline">{t('common.logout')}</span>
        </button>
      </div>
    </header>
  )
}
