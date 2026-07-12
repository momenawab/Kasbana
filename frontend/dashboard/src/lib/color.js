// Colour helpers for merchant-chosen fills (wallet cards, enroll-page
// backgrounds, accent buttons), where the client can pick literally anything and
// the UI has to stay readable on top of it.

/** Expand `abc` → `aabbcc`; returns '' for anything that isn't a 3/6-digit hex. */
function normalize(hex) {
  const h = (hex || '').trim().replace(/^#/, '')
  if (/^[0-9a-fA-F]{3}$/.test(h)) return h.replace(/./g, (c) => c + c)
  return /^[0-9a-fA-F]{6}$/.test(h) ? h : ''
}

/**
 * Perceived luminance of a hex colour → true if it's a "light" fill. Used to
 * flip foreground content to dark-on-light or light-on-dark so it stays visible
 * on whatever colour the client picks.
 *
 * Non-hex input (undefined, a gradient, `rgb(...)`) is *not* light — callers
 * that need "unknown means light" should use `isDarkColor`, which is false for
 * anything it can't parse.
 */
export function isLightColor(hex) {
  const h = normalize(hex)
  if (!h) return false
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.299 * r + 0.587 * g + 0.114 * b > 150
}

/**
 * True only for a colour we can parse *and* that is genuinely dark.
 *
 * Deliberately false for unparseable input: callers use this to decide whether
 * to flip a surface's text to light, and the default surface is light. Guessing
 * "dark" on a gradient we can't read would white-out text on a pale background —
 * strictly worse than leaving it alone.
 */
export function isDarkColor(hex) {
  return normalize(hex) !== '' && !isLightColor(hex)
}
