import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Globe, Sun, Moon } from 'lucide-react'
import { setLang } from '../lib/i18n'
import { useTheme, toggleTheme } from '../lib/theme'
import { useAuth } from '../hooks/useAuth'
import { arDigits, daysUntil } from '../lib/format'

export default function Topbar() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { merchant } = useAuth()
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
          type="button"
          role="switch"
          aria-checked={isDark}
          onClick={toggleTheme}
          className="relative flex h-8 w-16 shrink-0 items-center rounded-full bg-surface-2 ring-1 ring-inset ring-line transition hover:ring-violet/40"
          aria-label={isDark ? t('theme.toLight') : t('theme.toDark')}
          title={isDark ? t('theme.toLight') : t('theme.toDark')}
        >
          {/* Knob geometry is exact only because the track has no border: the
              flex halves (32px) and the knob's inset offsets then share one box. */}
          <span
            className={`absolute top-1 start-1 h-6 w-6 rounded-full bg-surface shadow-sm transition-transform duration-200 ${
              isDark ? 'translate-x-8 rtl:-translate-x-8' : 'translate-x-0'
            }`}
          />
          <span className="relative z-10 flex flex-1 items-center justify-center">
            <Sun size={14} className={isDark ? 'text-tx-3' : 'text-violet-d'} />
          </span>
          <span className="relative z-10 flex flex-1 items-center justify-center">
            <Moon size={14} className={isDark ? 'text-violet-d' : 'text-tx-3'} />
          </span>
        </button>
        <button
          onClick={toggleLang}
          className="flex items-center gap-1.5 rounded-ctl px-2.5 py-1.5 text-sm text-tx-2 transition hover:bg-surface-2 hover:text-tx"
          aria-label={t('common.language')}
        >
          <Globe size={16} />
          <span className="hidden sm:inline">{t('common.language')}</span>
        </button>
      </div>
    </header>
  )
}
