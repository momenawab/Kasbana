// WalletPreview — faithful Apple storeCard + Google loyalty previews that mirror
// the official PassKit / Google Wallet templates and reflect the merchant's
// editable pass design (notes 2-4). `design` is the wallet-design object; when a
// region's slot list is empty the built-in smart default is shown, matching the
// backend builders. Pure/presentational — updates as props change.
import { useTranslation } from 'react-i18next'
import { arDigits } from '../lib/format'

// Resolve a slot `source` token to a preview value (mirrors wallets/design.py).
function resolveValue(source, ctx) {
  if (!source) return ''
  if (source.startsWith('text:')) return source.slice(5)
  return source in ctx ? ctx[source] : source
}

function slotsOr(designSlots, fallback) {
  return designSlots && designSlots.length ? designSlots : fallback
}

function Field({ label, value, fg, labelColor, align = 'start' }) {
  return (
    <div className={`flex min-w-0 flex-col ${align === 'end' ? 'items-end text-right' : ''}`}>
      <span
        className="text-[9px] font-semibold uppercase tracking-wide"
        style={{ color: labelColor, opacity: 0.85 }}
      >
        {label}
      </span>
      <span className="truncate text-sm font-semibold" style={{ color: fg }}>
        {value}
      </span>
    </div>
  )
}

function StampGrid({ count, required, fg, emptyUrl, filledUrl }) {
  const n = Math.max(1, Math.min(required, 15))
  const custom = emptyUrl && filledUrl
  return (
    <div className="flex flex-wrap gap-1.5">
      {Array.from({ length: n }).map((_, i) => {
        const earned = i < count
        if (custom) {
          return (
            <img
              key={i}
              src={earned ? filledUrl : emptyUrl}
              alt=""
              className="h-5 w-5 object-contain"
            />
          )
        }
        return (
          <span
            key={i}
            className="h-4 w-4 rounded-full border"
            style={{
              borderColor: fg,
              background: earned ? fg : 'transparent',
              opacity: earned ? 1 : 0.45,
            }}
          />
        )
      })}
    </div>
  )
}

function Barcode({ fg, altText }) {
  return (
    <div className="mt-1 flex flex-col items-center">
      <div className="grid grid-cols-5 gap-0.5 rounded bg-white p-2">
        {Array.from({ length: 25 }).map((_, i) => (
          <span
            key={i}
            className="h-2.5 w-2.5"
            style={{ background: (i * 7) % 3 ? '#111' : 'transparent' }}
          />
        ))}
      </div>
      {altText && (
        <span className="mt-1 font-mono text-[11px] tracking-widest" style={{ color: fg }}>
          {altText}
        </span>
      )}
    </div>
  )
}

export default function WalletPreview({
  platform = 'APPLE',
  design = null,
  logoUrl,
  colorBg = '#0E1B2A',
  colorFg = '#FFFFFF',
  merchantName = 'Merchant',
  programName = 'Loyalty card',
  rewardTitle = 'Free reward',
  stampsRequired = 8,
  stampCount = 0,
  cardType = 'STAMP',
  shortCode = 'ABC123',
}) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const isStamp = cardType !== 'POINTS'
  const unit = isStamp ? 'Stamps' : 'Points'
  const goal = stampsRequired
  const remaining = Math.max(0, goal - stampCount)
  const labelColor = design?.label_color || colorFg

  const ctx = {
    balance: `${arDigits(stampCount, lang)}/${arDigits(goal, lang)}`,
    stamps: arDigits(stampCount, lang),
    points: arDigits(stampCount, lang),
    goal: arDigits(goal, lang),
    remaining: arDigits(remaining, lang),
    reward: rewardTitle,
    merchant: merchantName,
    program: programName,
  }
  const render = (slots) =>
    slots.map((s) => ({ label: s.label, value: resolveValue(s.source, ctx) }))
  const logoText = design?.apple_logo_text || (logoUrl ? '' : merchantName)
  const stripOn = isStamp && (design ? design.apple_strip_enabled : true)

  if (platform === 'GOOGLE') {
    const title = design?.google_title || merchantName
    const subtitle = design?.google_subtitle || programName
    const rows = render(design?.google_rows || [])
    return (
      <div className="w-[320px] overflow-hidden rounded-2xl border border-line bg-white shadow-bold">
        <div
          className="flex items-center gap-2 p-4"
          style={{ background: colorBg, color: colorFg }}
        >
          {logoUrl ? (
            <img src={logoUrl} alt="" className="h-9 w-9 rounded-full bg-white object-cover" />
          ) : (
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20 text-sm">
              {title.slice(0, 1)}
            </span>
          )}
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{title}</div>
            <div className="truncate text-xs opacity-80">{subtitle}</div>
          </div>
        </div>
        <div className="p-4">
          <div className="text-[10px] uppercase tracking-wide text-tx-3">{unit}</div>
          <div className="font-mono text-3xl tabular-nums text-ink">{ctx.balance}</div>
          {rows.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
              {rows.map((r, i) => (
                <div key={i}>
                  <div className="text-[10px] uppercase tracking-wide text-tx-3">{r.label}</div>
                  <div className="text-sm text-ink">{r.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-line p-4">
          <Barcode fg="#111" altText={shortCode} />
        </div>
      </div>
    )
  }

  // ── Apple storeCard ─────────────────────────────────────────────────────────
  const header = render(slotsOr(design?.apple_header, [{ label: unit, source: 'balance' }]))
  const primaryDefault = stripOn ? [] : [{ label: unit, source: isStamp ? 'stamps' : 'points' }]
  const primary = render(slotsOr(design?.apple_primary, primaryDefault))
  const secondaryDefault = stripOn
    ? [{ label: remaining ? 'Stamps left' : 'Reward ready', source: 'remaining' }]
    : [{ label: 'Goal', source: 'goal' }]
  const secondary = render(slotsOr(design?.apple_secondary, secondaryDefault))
  const auxiliary = render(
    slotsOr(design?.apple_auxiliary, rewardTitle ? [{ label: 'Reward', source: 'reward' }] : [])
  )

  return (
    <div
      className="w-[320px] rounded-2xl p-4 shadow-bold"
      style={{ background: colorBg, color: colorFg }}
    >
      {/* Logo + logo text + header fields */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {logoUrl ? (
            <img src={logoUrl} alt="" className="h-7 w-7 rounded-md bg-white object-cover" />
          ) : (
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/20 text-xs">
              {merchantName.slice(0, 1)}
            </span>
          )}
          {logoText && <span className="truncate text-sm font-semibold">{logoText}</span>}
        </div>
        <div className="flex gap-3">
          {header.map((f, i) => (
            <Field
              key={i}
              label={f.label}
              value={f.value}
              fg={colorFg}
              labelColor={labelColor}
              align="end"
            />
          ))}
        </div>
      </div>

      {/* Strip (stamp grid) */}
      {stripOn && (
        <div className="mt-3 rounded-lg bg-black/15 p-3">
          <StampGrid
            count={stampCount}
            required={goal}
            fg={colorFg}
            emptyUrl={design?.strip_empty_url}
            filledUrl={design?.strip_filled_url}
          />
        </div>
      )}

      {/* Primary field */}
      {primary.length > 0 && (
        <div className="mt-3 flex flex-col gap-2">
          {primary.map((f, i) => (
            <div key={i}>
              <div
                className="text-[9px] font-semibold uppercase tracking-wide"
                style={{ color: labelColor, opacity: 0.85 }}
              >
                {f.label}
              </div>
              <div className="font-mono text-2xl tabular-nums">{f.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Secondary + auxiliary */}
      {(secondary.length > 0 || auxiliary.length > 0) && (
        <div className="mt-3 flex justify-between gap-3">
          <div className="flex gap-4">
            {secondary.map((f, i) => (
              <Field key={i} label={f.label} value={f.value} fg={colorFg} labelColor={labelColor} />
            ))}
          </div>
          <div className="flex gap-4">
            {auxiliary.map((f, i) => (
              <Field
                key={i}
                label={f.label}
                value={f.value}
                fg={colorFg}
                labelColor={labelColor}
                align="end"
              />
            ))}
          </div>
        </div>
      )}

      {/* Barcode */}
      <div className="mt-4 border-t border-white/15 pt-3">
        <Barcode fg={colorFg} altText={shortCode} />
      </div>
    </div>
  )
}
