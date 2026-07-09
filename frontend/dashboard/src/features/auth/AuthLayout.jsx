// Dark split-screen auth shell (Login/Signup/Forgot/Reset/Invite): a branded
// violet→fuchsia panel on the left (desktop) and a dark glass form card on the
// right. The `.auth-dark` wrapper darkens the shared (light) form components.
import { useTranslation } from 'react-i18next'
import { Globe, Check, ShieldCheck, CreditCard } from 'lucide-react'
import { setLang } from '../../lib/i18n'

function StampCard({ t }) {
  // Decorative mock loyalty card echoing the logo (3 dots + a check badge).
  return (
    <div className="relative w-64 rotate-[-6deg] rounded-2xl bg-white/10 p-4 shadow-2xl ring-1 ring-white/15 backdrop-blur">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-white">{t('auth.cardName')}</p>
          <p className="text-[11px] text-white/60">{t('auth.cardMeta')}</p>
        </div>
        <img src="/logo.svg" alt="" className="h-8 w-8" />
      </div>
      <div className="mt-4 grid grid-cols-5 gap-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <span
            key={i}
            className={`flex h-8 items-center justify-center rounded-full text-[11px] font-bold ${
              i < 6
                ? 'bg-fuchsia text-white'
                : 'border border-dashed border-white/30 text-white/40'
            }`}
          >
            {i < 6 ? <Check size={13} /> : i + 1}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function AuthLayout({ title, subtitle, children, footer }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const toggleLang = () => setLang(lang === 'ar' ? 'en' : 'ar')
  const features = [t('auth.feature1'), t('auth.feature2'), t('auth.feature3'), t('auth.feature4')]

  return (
    <div className="flex min-h-screen bg-slate text-white">
      {/* Brand panel — desktop only */}
      <aside className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-gradient-to-br from-[#241a45] via-violet to-fuchsia p-12 lg:flex">
        {/* Soft decorative glow */}
        <div className="pointer-events-none absolute -top-28 -end-24 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -start-20 h-96 w-96 rounded-full bg-fuchsia/40 blur-3xl" />

        {/* Bigger logo lockup */}
        <div className="relative flex items-center gap-4">
          <img src="/logo.svg" alt="" className="h-24 w-24 drop-shadow-lg" />
          <span className="font-head text-[2.75rem] font-bold tracking-tight">{t('app.name')}</span>
        </div>

        <div className="relative">
          <h2 className="font-head text-4xl font-bold leading-[1.15]">{t('auth.tagline')}</h2>
          <p className="mt-4 max-w-md text-[15px] leading-relaxed text-white/75">
            {t('auth.description')}
          </p>

          <ul className="mt-8 flex flex-col gap-3.5">
            {features.map((f) => (
              <li key={f} className="flex items-start gap-3 text-[15px] text-white/90">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white/20">
                  <Check size={14} />
                </span>
                <span>{f}</span>
              </li>
            ))}
          </ul>

          {/* Decorative floating stamp card */}
          <div className="mt-10 hidden xl:block">
            <StampCard t={t} />
          </div>
        </div>

        {/* Copyright */}
        <div className="relative border-t border-white/15 pt-6 text-sm text-white/50">
          © {new Date().getFullYear()} {t('app.name')}
        </div>
      </aside>

      {/* Form panel */}
      <main className="auth-dark flex w-full flex-col lg:w-[54%]">
        <div className="flex justify-end p-4">
          <button
            type="button"
            onClick={toggleLang}
            className="inline-flex items-center gap-2 rounded-ctl px-3 py-1.5 text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
            aria-label={t('common.language')}
          >
            <Globe size={16} />
            <span>{t('common.language')}</span>
          </button>
        </div>

        <div className="flex flex-1 items-center justify-center px-4 pb-12">
          <div className="w-full max-w-sm">
            {/* Mobile logo (brand panel hidden below lg) — bigger */}
            <div className="mb-8 flex items-center justify-center gap-3 lg:hidden">
              <img src="/logo.svg" alt="" className="h-20 w-20 drop-shadow" />
              <span className="font-head text-4xl font-bold text-white">{t('app.name')}</span>
            </div>

            <div className="rounded-card border border-white/10 bg-white/5 p-7 shadow-bold backdrop-blur">
              <h1 className="font-head text-2xl font-bold text-white">{title}</h1>
              {subtitle && <p className="mt-1 text-sm text-white/60">{subtitle}</p>}
              <div className="mt-5">{children}</div>
            </div>

            {footer && <div className="mt-5 text-center text-sm text-white/60">{footer}</div>}

            {/* Trust line */}
            <div className="mt-6 flex items-center justify-center gap-5 text-xs text-white/45">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck size={14} /> {t('auth.secure')}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CreditCard size={14} /> {t('auth.noCard')}
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
