// ColorPicker (spec §10) — native swatch + validated hex input + brand presets.
// The hex field is a first-class way to enter a color: it accepts values with or
// without a leading '#', 3- or 6-digit hex, uppercases, and only commits once the
// value is a valid color — so typing a partial code never corrupts the swatch.
import { useEffect, useState } from 'react'
import { isLightColor } from '../lib/color'

const PRESETS = ['#0E1B2A', '#E0A23B', '#1C7C73', '#C75D43', '#16293D', '#FFFFFF']

// A full 6-digit hex → `#RRGGBB`, else null. Used while typing, so a partial or
// 3-digit value never commits mid-edit (which would rewrite the field length).
function fullHex(raw) {
  const h = raw.trim().replace(/^#/, '')
  return /^[0-9a-fA-F]{6}$/.test(h) ? `#${h.toUpperCase()}` : null
}

// Lenient normalize used on blur — also accepts 3-digit shorthand (`abc` → #AABBCC).
function normalizeHex(raw) {
  const h = raw.trim().replace(/^#/, '')
  if (fullHex(h)) return fullHex(h)
  if (/^[0-9a-fA-F]{3}$/.test(h)) {
    return `#${h
      .split('')
      .map((c) => c + c)
      .join('')
      .toUpperCase()}`
  }
  return null
}

export default function ColorPicker({ value = '#0E1B2A', onChange, label }) {
  // Local text state lets the user type freely (e.g. mid-edit "#0E1") without the
  // swatch jumping; we only push valid colors up to the parent.
  const [text, setText] = useState(value)
  // Keep the field in sync when the value changes from elsewhere (preset, swatch,
  // reset-to-inherit) — but not while the user is mid-edit on an invalid value.
  useEffect(() => {
    setText(value)
  }, [value])

  const commit = (raw) => {
    setText(raw)
    // Only a complete 6-digit hex propagates while typing — keeps the swatch and
    // the field length stable until the value is unambiguous.
    const hex = fullHex(raw)
    if (hex) onChange(hex)
  }

  const onBlur = () => {
    // On blur, also accept 3-digit shorthand; otherwise snap back to the last
    // committed value so the field is never left in an invalid state.
    const hex = normalizeHex(text)
    if (hex) onChange(hex)
    setText(hex || value)
  }

  const invalid = normalizeHex(text) === null
  // Badge contrasts the chosen swatch: dark-on-light for pale colors, the reverse
  // for dark ones — so the eyedropper never disappears into the fill.
  const light = isLightColor(value)

  return (
    <div>
      {label && <span className="mb-1.5 block text-sm text-tx-2">{label}</span>}
      <div className="flex flex-wrap items-center gap-3">
        {/* Tappable brand chip — clicking it opens the OS color picker. The
            eyedropper badge overlaps the swatch so it reads unmistakably as an
            interactive picker, not just a colored box. The mid-gray border keeps
            the chip visible even when its fill matches the card (white on white
            in light mode, near-black on the dark panel). */}
        <label
          className="group relative h-10 w-14 shrink-0 cursor-pointer overflow-hidden rounded-ctl border border-tx-3/50 shadow-sm transition hover:border-violet focus-within:border-violet focus-within:ring-2 focus-within:ring-violet/40"
          style={{ background: value }}
          title={label}
        >
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            aria-label={label || 'color'}
          />
          <span
            className={`pointer-events-none absolute bottom-1 end-1 flex h-4 w-4 items-center justify-center rounded-full shadow-sm ring-1 transition group-hover:scale-110 ${
              light ? 'bg-slate text-white ring-white/40' : 'bg-white text-slate ring-black/15'
            }`}
          >
            <svg
              viewBox="0 0 24 24"
              className="h-2.5 w-2.5"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0L12 2.69z" />
            </svg>
          </span>
        </label>
        <div className="relative">
          <span className="pointer-events-none absolute inset-y-0 start-2 flex items-center font-mono text-sm text-tx-3">
            #
          </span>
          <input
            type="text"
            value={text.replace(/^#/, '')}
            onChange={(e) => commit(e.target.value)}
            onBlur={onBlur}
            spellCheck={false}
            maxLength={7}
            aria-label={`${label || 'color'} hex code`}
            aria-invalid={invalid}
            placeholder="RRGGBB"
            className={`w-24 rounded-ctl border bg-surface ps-5 pe-2 py-2 font-mono text-sm uppercase text-tx outline-none focus:border-violet ${
              invalid ? 'border-danger' : 'border-line'
            }`}
          />
        </div>
        {/* Quick presets — wrap when the row runs out of room instead of
            overflowing a narrow column. The mid-gray border keeps every dot
            visible in both themes (the white and near-black presets would
            otherwise blend into the card); the active one gets a violet ring. */}
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((c) => {
            const active = value?.toUpperCase() === c.toUpperCase()
            return (
              <button
                key={c}
                type="button"
                onClick={() => onChange(c)}
                style={{ background: c }}
                className={`h-6 w-6 rounded-full border transition ${
                  active
                    ? 'border-violet ring-2 ring-violet/40'
                    : 'border-tx-3/60 hover:scale-110'
                }`}
                aria-label={c}
                aria-pressed={active}
                title={c}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
