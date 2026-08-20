import { useTranslation } from 'react-i18next'
import { setLang } from '../lib/i18n'

// Endonyms — deliberately never run through t(). Each label is written in its
// own script so both halves stay readable whichever language is active.
// `size` is an optical correction, not a preference: Arabic glyphs sit smaller
// on the em than Latin caps, so ع needs a step up to visually match EN.
const LANGS = [
  { code: 'en', label: 'EN', size: 'text-xs' },
  { code: 'ar', label: 'ع', size: 'text-sm' },
]

/**
 * Segmented language switch.
 *
 * Geometry is deliberately identical to the Topbar theme switch — same h-8/w-16
 * track, same 4px inset on the moving part — so the two preference controls read
 * as one pair rather than two unrelated widgets. Keep them in sync: changing the
 * track size here without changing it there is what makes them look mismatched.
 *
 * The filled half is the language you are *in*, not the one you'd switch to —
 * the old single button was labelled with its target ("العربية" while in
 * English), which reads as a statement of the current state and gets misread.
 *
 * `onDark` is for the auth panel, which is forced dark regardless of the app
 * theme, so the theme surface tokens would wash out against it.
 */
export default function LangSwitch({ onDark = false }) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  const track = onDark ? 'bg-white/10 ring-white/20' : 'bg-surface-2 ring-line'
  const idle = onDark ? 'text-white/60 hover:text-white' : 'text-tx-3 hover:text-tx'
  // Matches the theme switch's knob exactly: a raised surface-coloured circle
  // with the brand colour on top (not a violet fill). On the auth panel the
  // knob is pinned white — `bg-surface` follows the app theme, which would sink
  // it into the always-dark panel, and `.auth-dark` lightens `text-violet-d`
  // into something unreadable against white.
  const activeCls = onDark
    ? 'bg-white text-violet shadow-sm'
    : 'bg-surface text-violet-d shadow-sm'

  return (
    <div
      role="group"
      aria-label={t('common.language')}
      className={`flex h-8 w-16 shrink-0 items-center rounded-full p-1 ring-1 ring-inset ${track}`}
    >
      {LANGS.map(({ code, label, size }) => {
        const active = lang === code
        return (
          <button
            key={code}
            type="button"
            lang={code}
            onClick={() => setLang(code)}
            aria-pressed={active}
            className={
              `flex h-6 flex-1 items-center justify-center rounded-full ${size} font-semibold leading-none transition ` +
              (active ? activeCls : idle)
            }
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
