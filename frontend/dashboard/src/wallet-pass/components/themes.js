// PassThemes — the preset colour system for wallet passes. Every pass is built
// on a single bold accent (the way Apple Wallet does it): one background, one
// foreground, a muted variant for labels, and an accent for stamps / badges.
//
// A theme's `bg` may be a solid colour or a CSS gradient — both are valid for
// the `background` property, so PassCard applies it directly. `panel*` describes
// the white barcode/QR block, which stays light in both schemes so codes always
// scan. Light and dark schemes differ in how the page/chrome frames the pass and
// in the depth of the drop shadow; the deep, saturated pass backgrounds read
// well against either, matching the reference designs.

const rgba = (hex, a) => {
  const n = parseInt(hex.replace('#', ''), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

// name → { bg, fg, subHex, accent }. `sub` (muted label colour) is derived from
// the foreground so it always sits at a consistent, readable opacity.
const BASE = {
  red: { bg: 'linear-gradient(160deg, #F0453E 0%, #C4211C 100%)', fg: '#FFFFFF', accent: '#FFD25E' },
  orange: {
    bg: 'linear-gradient(160deg, #FB8B1E 0%, #EF6C00 100%)',
    fg: '#FFFFFF',
    accent: '#FFE0A3',
  },
  yellow: {
    bg: 'linear-gradient(160deg, #FBE07A 0%, #F4CE2E 100%)',
    fg: '#3A2E00',
    accent: '#B8860B',
  },
  green: { bg: 'linear-gradient(160deg, #14833E 0%, #0B5A2B 100%)', fg: '#FFFFFF', accent: '#8CE0AC' },
  blue: { bg: 'linear-gradient(160deg, #2E7DF6 0%, #1657CC 100%)', fg: '#FFFFFF', accent: '#B9D3FF' },
  purple: {
    bg: 'linear-gradient(160deg, #8A2E9A 0%, #5B1E66 100%)',
    fg: '#FFFFFF',
    accent: '#E7B6F2',
  },
  black: { bg: 'linear-gradient(160deg, #2C2C31 0%, #101013 100%)', fg: '#FFFFFF', accent: '#FFD25E' },
  brown: { bg: 'linear-gradient(160deg, #6B4A2E 0%, #3B2716 100%)', fg: '#FFFFFF', accent: '#E4C08A' },
  pink: { bg: 'linear-gradient(160deg, #F0157C 0%, #C60E66 100%)', fg: '#FFFFFF', accent: '#FFC2E2' },
  teal: { bg: 'linear-gradient(160deg, #5E96A0 0%, #3F757F 100%)', fg: '#FFFFFF', accent: '#CDEAEF' },
}

export const THEME_KEYS = Object.keys(BASE)

const PANEL = { panelBg: '#FFFFFF', panelFg: '#111111' }

// Resolve a theme input into the full colour set PassCard/children consume.
// `input` is a THEME_KEYS name, or a custom object { bg, fg, accent } for
// per-merchant colours (used when a saved card carries its own brand palette).
export function resolveTheme(input = 'blue') {
  const base = typeof input === 'string' ? BASE[input] || BASE.blue : { ...BASE.blue, ...input }
  const fg = base.fg || '#FFFFFF'
  return {
    bg: base.bg,
    fg,
    sub: rgba(fg, 0.66),
    hairline: rgba(fg, 0.16),
    accent: base.accent || fg,
    accentFg: base.fg === '#3A2E00' ? '#3A2E00' : '#1A1205',
    ...PANEL,
  }
}

// Swatches for a theme picker: [{ key, bg, fg }].
export const THEME_SWATCHES = THEME_KEYS.map((key) => ({
  key,
  bg: BASE[key].bg,
  fg: BASE[key].fg,
}))
