// WalletPreview (spec §11) — live Apple/Google pass mockups. Parent-controlled
// platform toggle; updates as props change. Functional fidelity (refined in P4).
import { useTranslation } from 'react-i18next'
import { arDigits } from '../lib/format'

function StampDots({ count, required, fg }) {
  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: required }).map((_, i) => (
        <span
          key={i}
          className="h-3.5 w-3.5 rounded-full border"
          style={{
            borderColor: fg,
            background: i < count ? fg : 'transparent',
            opacity: i < count ? 1 : 0.4,
          }}
        />
      ))}
    </div>
  )
}

export default function WalletPreview({
  platform = 'APPLE',
  logoUrl,
  colorBg = '#0E1B2A',
  colorFg = '#FFFFFF',
  merchantName = 'Merchant',
  programName = 'Loyalty card',
  rewardTitle = 'Free reward',
  stampsRequired = 8,
  stampCount = 0,
}) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const balance = `${arDigits(stampCount, lang)}/${arDigits(stampsRequired, lang)}`

  if (platform === 'GOOGLE') {
    return (
      <div className="w-[340px] overflow-hidden rounded-2xl border border-line bg-white shadow-bold">
        <div className="flex items-center gap-2 p-4" style={{ background: colorBg, color: colorFg }}>
          {logoUrl ? (
            <img src={logoUrl} alt="" className="h-8 w-8 rounded-full bg-white object-cover" />
          ) : (
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/20 text-xs">
              {merchantName.slice(0, 1)}
            </span>
          )}
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{merchantName}</div>
            <div className="truncate text-xs opacity-80">{programName}</div>
          </div>
        </div>
        <div className="p-4">
          <div className="text-xs text-tx-3">Balance</div>
          <div className="font-mono text-3xl tabular-nums text-ink">{balance}</div>
          <div className="mt-2 text-sm text-tx-2">{rewardTitle}</div>
          <div className="mt-4 h-10 rounded bg-[repeating-linear-gradient(90deg,#0E1B2A_0_2px,transparent_2px_4px)]" />
        </div>
      </div>
    )
  }

  // Apple storeCard
  return (
    <div
      className="w-[340px] rounded-2xl p-4 shadow-bold"
      style={{ background: colorBg, color: colorFg }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {logoUrl ? (
            <img src={logoUrl} alt="" className="h-7 w-7 rounded-md bg-white object-cover" />
          ) : (
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/20 text-xs">
              {merchantName.slice(0, 1)}
            </span>
          )}
          <span className="text-sm font-semibold">{merchantName}</span>
        </div>
        <span className="text-xs opacity-70">{programName}</span>
      </div>

      <div className="mt-5">
        <div className="text-[11px] uppercase tracking-wide opacity-70">Stamps</div>
        <div className="font-mono text-2xl tabular-nums">{balance}</div>
      </div>
      <div className="mt-3">
        <StampDots count={stampCount} required={stampsRequired} fg={colorFg} />
      </div>
      <div className="mt-4 text-xs opacity-80">Reward: {rewardTitle}</div>

      <div className="mt-4 flex justify-center rounded-lg bg-white p-2">
        <div className="h-10 w-40 bg-[repeating-linear-gradient(90deg,#0E1B2A_0_2px,transparent_2px_4px)]" />
      </div>
    </div>
  )
}
