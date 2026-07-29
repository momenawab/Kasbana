// WalletPreview — faithful Apple storeCard + Google loyalty previews that mirror
// the official PassKit / Google Wallet templates and reflect the merchant's
// editable pass design (notes 2-4 + templates). When a layout-locked `template`
// is active its fixed per-platform layout is rendered (positions locked); the
// Apple-vs-Google bottom-visual rule applies (stamps/image sit in the Apple
// strip at the TOP, in the Google hero under the header). The merchant's business
// name rides as Apple `logoText` beside the top-left brand logo; the platform
// (Kasbana) brand rides in the top-right header field (Apple has no right-side
// image slot), and as a bottom-right watermark on the Google hero.
//
// The Apple chrome follows the real storeCard: the strip is FULL-BLEED (edge to
// edge, no padding, no radius) at the pass's own aspect ratio, primary fields are
// overlaid ON it, secondary and auxiliary are two separate rows beneath, and the
// barcode is pinned to the bottom.
// Pure/presentational — updates as props change.
import { useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from '../lib/i18n'
import { QRCodeSVG } from 'qrcode.react'
import { arDigits } from '../lib/format'
import { isStampIcon, STAMP_ICON_PATHS } from './stampIcons'
import { APPLE_STRIP, GOOGLE_HERO, stampGeometry } from './passGeometry'

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

// The stamp strip, drawn in the backend's own coordinate space and scaled to fit
// by the viewBox — so it is full-bleed and correctly proportioned at any width.
// Priority mirrors the backend (wallets.stamp_icons): uploaded custom images win;
// else a built-in icon tinted with `stampColor`; else the drawn circles.
function StampStrip({
  count,
  required,
  fg,
  bg,
  emptyUrl,
  filledUrl,
  stampIcon,
  stampColor,
  layout,
  bgImage,
  stampsVisible = true,
  size = APPLE_STRIP,
}) {
  const [w, h] = size
  const n = Math.max(1, Math.min(required, 15))
  const earned = Math.max(0, Math.min(count, n))
  const custom = emptyUrl && filledUrl
  const paths = !custom && isStampIcon(stampIcon) ? STAMP_ICON_PATHS[stampIcon] : null
  const tint = stampColor || fg
  const { centers, radius, ring, iconSize } = stampGeometry(n, layout, size)
  // Artwork can hide the stamps entirely (a plain photo band); without artwork
  // the toggle is meaningless, so an empty strip is never rendered by accident.
  const showStamps = stampsVisible || !bgImage

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="block h-full w-full"
      preserveAspectRatio="xMidYMid slice"
      data-testid="stamp-strip"
      aria-hidden="true"
    >
      <rect width={w} height={h} fill={bg} />
      {/* Cover-crop, matching stamp_grid.cover_crop on the backend: `slice`
          scales to fill and centres the overflow rather than letterboxing, so
          one upload reads the same on the Apple strip and the Google hero. */}
      {bgImage && (
        <image
          href={bgImage}
          x={0}
          y={0}
          width={w}
          height={h}
          preserveAspectRatio="xMidYMid slice"
        />
      )}
      {showStamps &&
        centers.map(({ i, x, y }) => {
          const filled = i < earned
          if (custom) {
            return (
              <image
                key={i}
                href={filled ? filledUrl : emptyUrl}
                x={x - iconSize / 2}
                y={y - iconSize / 2}
                width={iconSize}
                height={iconSize}
                preserveAspectRatio="xMidYMid meet"
              />
            )
          }
          if (paths) {
            // STAMP_ICON_PATHS are authored on a 256×256 viewBox — scale into place.
            return (
              <g
                key={i}
                transform={`translate(${x - iconSize / 2} ${y - iconSize / 2}) scale(${iconSize / 256})`}
                opacity={filled ? 1 : 0.45}
              >
                <path d={filled ? paths.filled : paths.outline} fill={tint} />
              </g>
            )
          }
          return filled ? (
            <circle key={i} cx={x} cy={y} r={radius} fill={tint} />
          ) : (
            // The backend rings remaining stamps at alpha 150/255 — match it.
            <circle
              key={i}
              cx={x}
              cy={y}
              r={radius}
              fill="none"
              stroke={tint}
              strokeOpacity={150 / 255}
              strokeWidth={ring}
            />
          )
        })}
    </svg>
  )
}

// A real QR — the pass shows one, so the preview shows one. `value` is what the
// pass encodes; `altText` is the short human code a cashier can type instead.
function Barcode({ value, altText, fg, size = 76 }) {
  return (
    <div className="flex flex-col items-center">
      <div className="rounded-md bg-white p-1.5">
        <QRCodeSVG
          value={value || altText || '—'}
          size={size}
          level="M"
          bgColor="#FFFFFF"
          fgColor="#000000"
          data-testid="pass-qr"
        />
      </div>
      {altText && (
        <span className="mt-1.5 font-mono text-[11px] tracking-[0.2em]" style={{ color: fg }}>
          {altText}
        </span>
      )}
    </div>
  )
}

// One Apple field: small caps label above the value (PassKit's field style).
function Field({ label, value, fg, labelColor, onStrip = false }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span
        className="truncate text-[9px] font-semibold uppercase tracking-[0.06em]"
        style={{
          color: labelColor,
          opacity: 0.85,
          textShadow: onStrip ? '0 1px 2px rgba(0,0,0,.55)' : undefined,
        }}
      >
        {label}
      </span>
      <span
        className="truncate text-[13px] font-semibold leading-tight"
        style={{ color: fg, textShadow: onStrip ? '0 1px 2px rgba(0,0,0,.55)' : undefined }}
      >
        {value}
      </span>
    </div>
  )
}

// Platform (Kasbana) logo at the bottom-right of the pass. `url` is the real
// asset when configured; otherwise a drawn PLACEHOLDER badge (the slot is wired).
function PlatformLogo({ url, fg }) {
  return (
    <div className="pointer-events-none absolute bottom-1.5 right-2">
      {url ? (
        // Attribution, not branding — it sits under the merchant's own identity,
        // so it is capped on BOTH axes. Width alone let a short, wide logo run
        // most of the card's width; the height cap is what actually keeps it a
        // badge rather than a second brand mark.
        <img src={url} alt="" className="max-h-[14px] max-w-[64px] object-contain opacity-90" />
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

// A true miniature: the card is always laid out at its natural 320px width and
// then scaled, so a tile is the same card seen smaller — never a re-flowed one.
// The wrapper reserves exactly the scaled box (a bare `transform` would still
// reserve the full-size one, padding every tile).
function Scaled({ scale, children }) {
  const ref = useRef(null)
  const [height, setHeight] = useState(0)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const measure = () => setHeight(el.offsetHeight)
    measure()
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    // Until the first measurement lands, leave the box auto-height: a hard `height:
    // 0` would collapse the tile to nothing if measuring ever failed, and an
    // over-tall tile is a far better failure than an invisible one.
    <div style={{ width: 320 * scale, height: height ? height * scale : undefined }}>
      <div
        ref={ref}
        style={{ width: 320, transform: `scale(${scale})`, transformOrigin: 'top left' }}
      >
        {children}
      </div>
    </div>
  )
}

export default function WalletPreview({
  platform = 'APPLE',
  design = null,
  template = null,
  platformLogoUrl = '/stampn-lockup.png',
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
  barcodeValue = '',
  scale = 1,
}) {
  const { i18n } = useTranslation()
  const lang = i18n.language
  const isStamp = cardType !== 'POINTS'
  const unit = isStamp ? 'Stamps' : 'Points'
  const goal = stampsRequired
  const remaining = Math.max(0, goal - stampCount)
  const labelColor = design?.label_color || colorFg
  const bottomImage = design?.bottom_image_url || ''
  const stripBg = design?.strip_bg_color || darkenHex(colorBg)

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
      // The Google card body is white in the real wallet, so its text/borders are
      // fixed light-theme colors — theme tokens would go white-on-white in dark mode.
      <div className="relative w-[320px] overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-bold">
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
        {/* Bottom visual (stamp counter or photo) in the hero banner — the hero has
            its own canvas on the backend, so it gets its own aspect ratio here. */}
        {showHero && (
          <div className="w-full" style={{ aspectRatio: `${GOOGLE_HERO[0]} / ${GOOGLE_HERO[1]}` }}>
            {tpl && bottomVisual === 'image' ? (
              bottomImage ? (
                <img src={bottomImage} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="h-full w-full" style={{ background: stripBg }} />
              )
            ) : (
              <StampStrip
                count={stampCount}
                required={goal}
                fg={colorFg}
                bg={stripBg}
                emptyUrl={design?.strip_empty_url}
                filledUrl={design?.strip_filled_url}
                stampIcon={design?.stamp_icon}
                stampColor={design?.stamp_color}
                layout={design?.stamp_layout}
                bgImage={design?.strip_bg_image_url}
                stampsVisible={design?.strip_stamps_visible !== false}
                size={GOOGLE_HERO}
              />
            )}
          </div>
        )}
        <div className="p-4">
          <div className="text-[10px] uppercase tracking-wide text-[#555]">{unit}</div>
          <div className="font-mono text-3xl tabular-nums text-[#111]">{ctx.balance}</div>
          {rows.length > 0 && (
            <div className="mt-3 flex flex-col gap-2 border-t border-[#e5e7eb] pt-3">
              {rows.map((r, i) => (
                <div key={i}>
                  <div className="text-[10px] uppercase tracking-wide text-[#555]">{r.label}</div>
                  <div className="text-sm text-[#111]">{r.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="border-t border-[#e5e7eb] p-4">
          <Barcode fg="#111" value={barcodeValue} altText={shortCode} />
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

  const card = (
    // No padding on the card itself — the strip has to reach the edges, so every
    // other row carries its own inset instead.
    <div
      className="relative flex w-[320px] flex-col overflow-hidden rounded-2xl shadow-bold"
      style={{ background: colorBg, color: colorFg }}
      data-testid="apple-pass"
    >
      {/* Logo + logo text + header fields */}
      <div className="flex items-center justify-between gap-2 px-4 pb-2.5 pt-3.5">
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
        <div className="flex shrink-0 gap-3">
          {header.map((f, i) => (
            <div key={i} className="flex flex-col items-end text-right">
              <span
                className="text-[9px] font-semibold uppercase tracking-[0.06em]"
                style={{ color: labelColor, opacity: 0.85 }}
              >
                {f.label}
              </span>
              <span className="text-sm font-semibold" style={{ color: colorFg }}>
                {f.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Strip — full-bleed, locked to the pass's own aspect ratio, butted straight
          under the header. Apple overlays the primary fields ON it. */}
      {stripOn && (
        <div
          className="relative w-full"
          style={{ aspectRatio: `${APPLE_STRIP[0]} / ${APPLE_STRIP[1]}` }}
          data-testid="apple-strip"
        >
          {stripIsImage ? (
            bottomImage ? (
              <img src={bottomImage} alt="" className="h-full w-full object-cover" />
            ) : (
              <div className="h-full w-full" style={{ background: stripBg }} />
            )
          ) : (
            <StampStrip
              count={stampCount}
              required={goal}
              fg={colorFg}
              bg={stripBg}
              emptyUrl={design?.strip_empty_url}
              filledUrl={design?.strip_filled_url}
              stampIcon={design?.stamp_icon}
              stampColor={design?.stamp_color}
              layout={design?.stamp_layout}
              bgImage={design?.strip_bg_image_url}
              stampsVisible={design?.strip_stamps_visible !== false}
              size={APPLE_STRIP}
            />
          )}
          {primary.length > 0 && (
            <div
              className="absolute inset-0 flex items-start gap-6 px-4 pt-2"
              data-testid="apple-primary"
            >
              {primary.map((f, i) => (
                <Field
                  key={i}
                  label={f.label}
                  value={f.value}
                  fg={colorFg}
                  labelColor={labelColor}
                  onStrip
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* No strip → the primary fields take their normal place in the flow. */}
      {!stripOn && primary.length > 0 && (
        <div className="flex gap-6 px-4 pt-1" data-testid="apple-primary">
          {primary.map((f, i) => (
            <div key={i} className="flex min-w-0 flex-col">
              <span
                className="text-[9px] font-semibold uppercase tracking-[0.06em]"
                style={{ color: labelColor, opacity: 0.85 }}
              >
                {f.label}
              </span>
              <span className="font-mono text-2xl tabular-nums">{f.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Secondary and auxiliary are two SEPARATE rows on a real pass, each
          running left-to-right — not one row split down the middle. */}
      {secondary.length > 0 && (
        <div className="flex gap-6 px-4 pt-3" data-testid="apple-secondary">
          {secondary.map((f, i) => (
            <Field key={i} label={f.label} value={f.value} fg={colorFg} labelColor={labelColor} />
          ))}
        </div>
      )}
      {auxiliary.length > 0 && (
        <div className="flex gap-6 px-4 pt-2.5" data-testid="apple-auxiliary">
          {auxiliary.map((f, i) => (
            <Field key={i} label={f.label} value={f.value} fg={colorFg} labelColor={labelColor} />
          ))}
        </div>
      )}

      {/* Barcode — Apple pins it to the very bottom; nothing sits below it, and the
          platform brand is in the header field above, so there's no footer here. */}
      <div className="mt-auto px-4 pb-3.5 pt-4">
        <Barcode fg={colorFg} value={barcodeValue} altText={shortCode} />
      </div>
    </div>
  )

  return scale === 1 ? card : <Scaled scale={scale}>{card}</Scaled>
}
