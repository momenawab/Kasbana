// WalletPreview — faithful Apple storeCard + Google loyalty previews that mirror
// the official PassKit / Google Wallet templates and reflect the merchant's
// editable pass design (notes 2-4 + templates). When a layout-locked `template`
// is active its fixed per-platform layout is rendered (positions locked); the
// Apple-vs-Google bottom-visual rule applies (stamps/image sit in the Apple
// strip at the TOP, in the Google hero under the header). The merchant's business
// name rides as Apple `logoText` beside the top-left brand logo; the platform
// (Kasbana) brand rides in the top-right header field (Apple has no right-side
// image slot), and as a bottom-left watermark on the Google hero.
// Pure/presentational — updates as props change.
import { useTranslation } from 'react-i18next'
import { arDigits } from '../lib/format'
import { isStampIcon } from './stampIcons'
import StampGlyph from './StampGlyph'

// Resolve a slot `source` token to a preview value (mirrors wallets/design.py).
function resolveValue(source, ctx) {
  if (!source) return ''
  if (source.startsWith('text:')) return source.slice(5)
  return source in ctx ? ctx[source] : source
}

// Replace {token} placeholders in a label (mirrors templates.interpolate).
function interpolate(label, ctx) {
  if (!label || label.indexOf('{') === -1) return label
  return label.replace(/\{(\w+)\}/g, (_, k) => (k in ctx ? String(ctx[k]) : ''))
}

function slotsOr(designSlots, fallback) {
  return designSlots && designSlots.length ? designSlots : fallback
}

// Darken a #RRGGBB toward black (mirrors the backend strip default) so the strip
// band reads as its own row when no explicit strip color is set.
function darkenHex(hex, factor = 0.82) {
  const m = (hex || '').match(/^#?([0-9a-f]{6})$/i)
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const r = Math.round(((n >> 16) & 255) * factor)
  const g = Math.round(((n >> 8) & 255) * factor)
  const b = Math.round((n & 255) * factor)
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`
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

// Stamp strip preview. Priority mirrors the backend (wallets.stamp_icons):
// uploaded custom images win; else a built-in icon tinted with `stampColor`;
// else the drawn circles. `stampColor` (when set) also recolors the circles.
function StampGrid({ count, required, fg, emptyUrl, filledUrl, stampIcon, stampColor }) {
  const n = Math.max(1, Math.min(required, 15))
  const custom = emptyUrl && filledUrl
  const builtIn = !custom && isStampIcon(stampIcon)
  const tint = stampColor || fg
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
        if (builtIn) {
          return (
            <StampGlyph
              key={i}
              icon={stampIcon}
              filled={earned}
              faded={!earned}
              color={tint}
              size={20}
            />
          )
        }
        return (
          <span
            key={i}
            className="h-4 w-4 rounded-full border"
            style={{
              borderColor: tint,
              background: earned ? tint : 'transparent',
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

// Platform (Kasbana) logo at the bottom-left of the pass. `url` is the real
// asset when configured; otherwise a drawn PLACEHOLDER badge (the slot is wired).
function PlatformLogo({ url, fg }) {
  return (
    <div className="pointer-events-none absolute bottom-1.5 left-2">
      {url ? (
        <img src={url} alt="" className="h-4 max-w-[64px] object-contain opacity-80" />
      ) : (
        <span
          className="rounded-[3px] px-1 py-px text-[7px] font-bold uppercase tracking-wide"
          style={{ color: fg, border: `1px solid ${fg}`, opacity: 0.4 }}
        >
          Logo
        </span>
      )}
    </div>
  )
}

export default function WalletPreview({
  platform = 'APPLE',
  design = null,
  template = null,
  platformLogoUrl = '',
  platformLabel = 'Stampn',
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
  const bottomImage = design?.bottom_image_url || ''

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
  const tplRender = (slots) =>
    (slots || []).map((s) => ({
      label: interpolate(s.label, ctx),
      value: resolveValue(s.source, ctx),
    }))
  // logoText rides beside the top-left logo → the merchant's business name (the
  // brand customers recognise), mirroring wallets.apple.passdata. A branded
  // merchant may override the wording; the platform brand lives in the top-right
  // header field instead (see below).
  const logoText = design?.apple_logo_text || merchantName

  // Template mode locks the layout: regions come from the template, and the
  // strip/hero behaviour is pinned to its bottom_visual.
  const tpl = template && template.key && template.key !== 'custom' ? template : null
  const bottomVisual = tpl?.bottom_visual || 'none'
  const hasBottom = tpl ? ['stamps', 'image'].includes(bottomVisual) : false

  if (platform === 'GOOGLE') {
    const title = tpl ? resolveValue(tpl.google?.title, ctx) : design?.google_title || merchantName
    const subtitle = tpl
      ? resolveValue(tpl.google?.subtitle, ctx)
      : design?.google_subtitle || programName
    const rows = tpl ? tplRender(tpl.google?.rows) : render(design?.google_rows || [])
    const showHero = tpl ? hasBottom : isStamp && design?.google_stamp_hero
    return (
      <div className="relative w-[320px] overflow-hidden rounded-2xl border border-line bg-white shadow-bold">
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
        {/* Bottom visual (stamp counter or photo) in the hero banner */}
        {showHero && (
          <div
            className="px-4 py-3"
            style={{ background: design?.strip_bg_color || darkenHex(colorBg) }}
          >
            {tpl && bottomVisual === 'image' ? (
              bottomImage ? (
                <img src={bottomImage} alt="" className="max-h-20 w-full object-contain" />
              ) : null
            ) : (
              <StampGrid
                count={stampCount}
                required={goal}
                fg={colorFg}
                emptyUrl={design?.strip_empty_url}
                filledUrl={design?.strip_filled_url}
                stampIcon={design?.stamp_icon}
                stampColor={design?.stamp_color}
              />
            )}
          </div>
        )}
        <div className="p-4">
          <div className="text-[10px] uppercase tracking-wide text-tx-3">{unit}</div>
          <div className="font-mono text-3xl tabular-nums text-tx">{ctx.balance}</div>
          {rows.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 border-t border-line pt-3">
              {rows.map((r, i) => (
                <div key={i}>
                  <div className="text-[10px] uppercase tracking-wide text-tx-3">{r.label}</div>
                  <div className="text-sm text-tx">{r.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-line p-4">
          <Barcode fg="#111" altText={shortCode} />
        </div>
        <PlatformLogo url={platformLogoUrl} fg="#555" />
      </div>
    )
  }

  // ── Apple storeCard ─────────────────────────────────────────────────────────
  let header, primary, secondary, auxiliary, stripOn, stripIsImage
  if (tpl) {
    header = tplRender(tpl.apple?.header)
    primary = tplRender(tpl.apple?.primary)
    secondary = tplRender(tpl.apple?.secondary)
    auxiliary = tplRender(tpl.apple?.auxiliary)
    stripOn = hasBottom
    stripIsImage = bottomVisual === 'image'
  } else {
    const stripOnFree = isStamp && (design ? design.apple_strip_enabled : true)
    header = render(slotsOr(design?.apple_header, [{ label: unit, source: 'balance' }]))
    const primaryDefault = stripOnFree
      ? []
      : [{ label: unit, source: isStamp ? 'stamps' : 'points' }]
    primary = render(slotsOr(design?.apple_primary, primaryDefault))
    const secondaryDefault = stripOnFree
      ? [{ label: remaining ? 'Stamps left' : 'Reward ready', source: 'remaining' }]
      : [{ label: 'Goal', source: 'goal' }]
    secondary = render(slotsOr(design?.apple_secondary, secondaryDefault))
    auxiliary = render(
      slotsOr(design?.apple_auxiliary, rewardTitle ? [{ label: 'Reward', source: 'reward' }] : [])
    )
    stripOn = stripOnFree
    stripIsImage = false
  }

  // Platform attribution owns the only top-right slot Apple's storeCard offers —
  // a header field — replacing the numeric balance (the strip + secondary already
  // convey progress). Mirrors wallets.apple.passdata's header override.
  if (platformLabel) header = [{ label: '', value: platformLabel }]

  return (
    <div
      className="relative w-[320px] rounded-2xl p-4 shadow-bold"
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

      {/* Strip — the bottom visual: stamp grid (stamps) or full-width image
          (image), on its own band so it doesn't blend in. On Apple this lives
          at the TOP (Apple pins the barcode to the very bottom). */}
      {stripOn && (
        <div
          className="mt-3 rounded-lg p-3"
          style={{ background: design?.strip_bg_color || darkenHex(colorBg) }}
        >
          {stripIsImage ? (
            bottomImage ? (
              <img src={bottomImage} alt="" className="max-h-24 w-full object-contain" />
            ) : null
          ) : (
            <StampGrid
              count={stampCount}
              required={goal}
              fg={colorFg}
              emptyUrl={design?.strip_empty_url}
              filledUrl={design?.strip_filled_url}
              stampIcon={design?.stamp_icon}
              stampColor={design?.stamp_color}
            />
          )}
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

      {/* Barcode — Apple pins it to the very bottom; nothing sits below it, and
          the platform brand is in logoText above, so there's no footer here. */}
      <div className="mt-4 border-t border-white/15 pt-3">
        <Barcode fg={colorFg} altText={shortCode} />
      </div>
    </div>
  )
}
