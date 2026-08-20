// PassBarcode — the reusable code block for a pass. QR delegates to PassQR (a
// real scannable code). Code128 / PDF417 / Aztec are rendered as faithful
// visual stand-ins: the dashboard ships only a QR encoder, so 1D/2D formats are
// drawn deterministically from the value (same value → same pattern) to preview
// the on-pass look. Swap in a real encoder later without touching call sites.
import PassQR from './PassQR'

// Deterministic PRNG (mulberry32) seeded from the value string, so a given code
// always renders the same pattern.
function seeded(str) {
  let h = 1779033703 ^ str.length
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  let a = h >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function Code128({ value }) {
  const rnd = seeded(value || 'code128')
  const bars = Array.from({ length: 46 }, () => 1 + Math.round(rnd() * 2.4)) // widths 1–3
  return (
    <div className="flex h-11 items-stretch justify-center gap-[2px]" aria-hidden>
      {bars.map((w, i) => (
        <span
          key={i}
          style={{ width: w, background: i % 2 ? 'transparent' : '#111' }}
          className="inline-block"
        />
      ))}
    </div>
  )
}

function Pdf417({ value }) {
  const rnd = seeded(value || 'pdf417')
  const rows = 5
  const cols = 26
  return (
    <div className="flex flex-col gap-[2px]" aria-hidden>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-[2px]">
          {Array.from({ length: cols }).map((_, c) => (
            <span
              key={c}
              style={{ width: 3, height: 6, background: rnd() > 0.5 ? '#111' : 'transparent' }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

function Aztec({ value }) {
  const rnd = seeded(value || 'aztec')
  const n = 11
  const mid = (n - 1) / 2
  return (
    <div
      className="grid gap-[2px]"
      style={{ gridTemplateColumns: `repeat(${n}, 6px)` }}
      aria-hidden
    >
      {Array.from({ length: n * n }).map((_, i) => {
        const r = Math.floor(i / n)
        const c = i % n
        const ring = Math.max(Math.abs(r - mid), Math.abs(c - mid))
        // Concentric bullseye in the centre, pseudo-random modules outside it.
        const on = ring <= 2 ? ring % 2 === 0 : rnd() > 0.48
        return <span key={i} style={{ width: 6, height: 6, background: on ? '#111' : 'transparent' }} />
      })}
    </div>
  )
}

export default function PassBarcode({ value = '', format = 'qr', code, size, theme }) {
  if (format === 'qr') return <PassQR value={value} code={code} size={size} theme={theme} />
  const Pattern = format === 'pdf417' ? Pdf417 : format === 'aztec' ? Aztec : Code128
  const label = code || value
  return (
    <div className="flex flex-col items-center">
      <div className="pass-qr-fade flex items-center justify-center rounded-2xl bg-white px-4 py-3 shadow-sm">
        <Pattern value={value} />
      </div>
      {label && (
        <span
          className="mt-2 font-mono text-[11px] tracking-widest"
          style={{ color: theme?.sub || 'rgba(255,255,255,0.9)' }}
        >
          {label}
        </span>
      )}
    </div>
  )
}
