// A plain textarea JSON editor with live parse feedback.
//
// Deliberately not a code-editor dependency: the overlays are small documents,
// and the failure an admin actually hits is a trailing comma or a stray quote —
// which a parse message pinned under the field catches just as well as a syntax
// highlighter, without adding a megabyte to the console bundle.
//
// The value is held as TEXT, not as a parsed object. Round-tripping through
// JSON.parse on every keystroke would reformat the document under the cursor and
// make it impossible to type a half-finished key.
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check } from 'lucide-react'

function formatJson(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return ''
  }
}

export default function JsonEditor({ label, hint, value, onChange, rows = 18 }) {
  const [text, setText] = useState(() => formatJson(value))

  // Re-seed when the card selection changes underneath us. Comparing formatted
  // text (not object identity) avoids clobbering an in-progress edit every time
  // the parent re-renders with an equivalent object.
  const incoming = useMemo(() => formatJson(value), [value])
  useEffect(() => {
    setText((current) => (current.trim() === incoming.trim() ? current : incoming))
  }, [incoming])

  const parsed = useMemo(() => {
    const trimmed = text.trim()
    if (!trimmed) return { ok: true, value: {} }
    try {
      const out = JSON.parse(trimmed)
      if (out === null || typeof out !== 'object' || Array.isArray(out)) {
        return { ok: false, error: 'Must be a JSON object — start with { and end with }.' }
      }
      return { ok: true, value: out }
    } catch (err) {
      return { ok: false, error: err.message }
    }
  }, [text])

  const handle = (next) => {
    setText(next)
    const trimmed = next.trim()
    if (!trimmed) return onChange({}, true)
    try {
      const out = JSON.parse(trimmed)
      if (out && typeof out === 'object' && !Array.isArray(out)) onChange(out, true)
      else onChange(null, false)
    } catch {
      // Invalid mid-edit is normal; tell the parent so Save stays disabled, but
      // never discard what the admin has typed.
      onChange(null, false)
    }
  }

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label className="text-sm font-semibold text-tx">{label}</label>
        {parsed.ok ? (
          <span className="flex items-center gap-1 text-xs text-success">
            <Check size={12} /> valid JSON
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-danger">
            <AlertTriangle size={12} /> invalid
          </span>
        )}
      </div>
      {hint && <p className="mb-1.5 text-xs text-tx-3">{hint}</p>}
      <textarea
        value={text}
        onChange={(e) => handle(e.target.value)}
        rows={rows}
        spellCheck={false}
        placeholder="{}"
        className={`w-full rounded-ctl border bg-bg p-3 font-mono text-xs leading-relaxed text-tx outline-none focus:border-brand ${
          parsed.ok ? 'border-line' : 'border-danger'
        }`}
      />
      {!parsed.ok && <p className="mt-1 text-xs text-danger">{parsed.error}</p>}
    </div>
  )
}
