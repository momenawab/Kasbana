import { useTranslation } from 'react-i18next'
import { arDigits } from '../lib/format'

// KpiTile (spec §10/§Direction-C) — solid color block, oversized mono number,
// delta chip at the top-end. tone picks the block color.
const TONES = {
  amber: 'bg-amber text-ink',
  teal: 'bg-teal text-white',
  clay: 'bg-clay text-white',
  ink: 'bg-ink text-white',
}

export default function KpiTile({ label, value, deltaPct, icon: Icon, tone = 'amber' }) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const up = typeof deltaPct === 'number' && deltaPct >= 0
  const onDark = tone !== 'amber'

  return (
    <div className={`relative overflow-hidden rounded-card p-5 shadow-bold ${TONES[tone]}`}>
      <div className="flex items-start justify-between">
        <span className={`text-sm ${onDark ? 'text-white/80' : 'text-ink/70'}`}>{label}</span>
        {typeof deltaPct === 'number' && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
              onDark ? 'bg-white/15 text-white' : 'bg-ink/10 text-ink'
            }`}
          >
            {up ? '▲' : '▼'} {arDigits(Math.abs(deltaPct), lang)}%
          </span>
        )}
      </div>
      <div className="mt-3 font-mono text-[40px] leading-none tabular-nums md:text-[44px]">
        {arDigits(value, lang)}
      </div>
      {Icon && (
        <Icon
          size={64}
          className={`absolute -bottom-3 -end-2 ${onDark ? 'text-white/10' : 'text-ink/10'}`}
        />
      )}
    </div>
  )
}
