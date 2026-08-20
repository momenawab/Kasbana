// A compact wallet-pass preview for the test-card builder.
//
// Deliberately NOT a port of the dashboard's WalletPreview (526 lines, pulling in
// stamp-icon paths, pass geometry and i18n). This is a sales pitch aid — it needs
// to look right at a glance while the rep types, not to be pixel-faithful. The
// real pass is one tap away via the wallet buttons.
import { Apple, Smartphone } from 'lucide-react'

function Stamp({ filled, fg }) {
  return (
    <span
      className="flex h-6 w-6 items-center justify-center rounded-full border text-[10px]"
      style={{
        borderColor: fg,
        background: filled ? fg : 'transparent',
        color: filled ? 'transparent' : fg,
        opacity: filled ? 1 : 0.45,
      }}
    >
      ★
    </span>
  )
}

export default function CardPreview({ platform, form, merchantName }) {
  const bg = form.color_bg || '#0E1B2A'
  const fg = form.color_fg || '#FFFFFF'
  const total = Math.min(Number(form.stamps_required) || 8, 12)
  const filled = Math.min(Number(form.preview_stamps) || 0, total)
  const isApple = platform === 'APPLE'

  return (
    <div
      className="w-full max-w-[320px] overflow-hidden shadow-lg"
      style={{
        background: bg,
        color: fg,
        borderRadius: isApple ? 14 : 10,
      }}
    >
      {/* Header — logo + brand */}
      <div className="flex items-center gap-2 px-4 pt-4">
        {form.logo_url ? (
          <img src={form.logo_url} alt="" className="h-7 w-7 rounded-md object-cover" />
        ) : (
          <div
            className="flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold"
            style={{ background: fg, color: bg }}
          >
            {(merchantName || '?').trim()[0]?.toUpperCase() || '?'}
          </div>
        )}
        <span className="truncate text-sm font-semibold" style={{ color: fg }}>
          {merchantName || 'Business name'}
        </span>
      </div>

      {/* Hero */}
      {form.hero_image_url && (
        <img src={form.hero_image_url} alt="" className="mt-3 h-24 w-full object-cover" />
      )}

      {/* Program + reward */}
      <div className="px-4 pb-1 pt-3">
        <div className="text-[10px] uppercase tracking-wide" style={{ color: fg, opacity: 0.6 }}>
          {form.type === 'POINTS' ? 'Points program' : 'Stamp card'}
        </div>
        <div className="truncate text-base font-bold" style={{ color: fg }}>
          {form.name || 'Program name'}
        </div>
        <div className="mt-0.5 truncate text-xs" style={{ color: fg, opacity: 0.8 }}>
          {form.reward_title || 'Your reward'}
        </div>
      </div>

      {/* Stamps */}
      {form.type === 'STAMP' && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-3 pt-2">
          {Array.from({ length: total }).map((_, i) => (
            <Stamp key={i} filled={i < filled} fg={fg} />
          ))}
        </div>
      )}

      {/* Barcode strip — the visual anchor every wallet pass has */}
      <div
        className="mt-1 flex items-center justify-center gap-2 py-3"
        style={{ background: '#FFFFFF' }}
      >
        <div className="h-12 w-12 rounded bg-[repeating-linear-gradient(90deg,#111_0_2px,#fff_2px_4px)]" />
        <span className="text-[10px] text-neutral-500">
          {isApple ? (
            <span className="flex items-center gap-1">
              <Apple size={11} /> Apple Wallet
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <Smartphone size={11} /> Google Wallet
            </span>
          )}
        </span>
      </div>
    </div>
  )
}
