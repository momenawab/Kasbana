import { useTranslation } from 'react-i18next'
import { arDigits } from '../lib/format'

// KpiTile — calm surface card with a solid brand icon chip, oversized mono
// number, and a signed delta chip. `tone` picks the icon-chip color; the
// card itself is theme-aware (light/dark) so the numbers stay comfortable.
const CHIPS = {
  violet: 'bg-violet',
  teal: 'bg-teal',
  fuchsia: 'bg-fuchsia',
  slate: 'bg-gradient-to-br from-violet to-fuchsia', // brand duotone
}

export default function KpiTile({ label, value, deltaPct, icon: Icon, tone = 'violet' }) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const up = typeof deltaPct === 'number' && deltaPct >= 0

  return (
    <div className="theme-t relative overflow-hidden rounded-card border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between">
        <span
          className={`flex h-11 w-11 items-center justify-center rounded-ctl text-white shadow-pop ${CHIPS[tone] || CHIPS.violet}`}
        >
          {Icon && <Icon size={22} />}
        </span>
        {typeof deltaPct === 'number' && (
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold font-num ${
              up ? 'bg-teal/10 text-teal' : 'bg-danger/10 text-danger'
            }`}
          >
            {up ? '▲' : '▼'} {arDigits(Math.abs(deltaPct), lang)}%
          </span>
        )}
      </div>
      <div className="mt-4 font-mono text-[34px] font-semibold leading-none tabular-nums text-tx md:text-[40px]">
        {arDigits(value, lang)}
      </div>
      <div className="mt-1.5 text-sm text-tx-2">{label}</div>
    </div>
  )
}
