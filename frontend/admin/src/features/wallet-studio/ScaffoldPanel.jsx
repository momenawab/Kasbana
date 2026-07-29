// "Here is the pass you already have" — the JSON tab's starting point.
//
// A card designed in the Editor has no overlay, so without this the JSON tab
// would open on an empty `{}` and an admin would have to retype the pass from
// memory to change one field. This shows what the card renders *today*, and
// copies it into the overlay in one click.
//
// It is deliberately the TOKEN form ({balance}, not "3/8") and already has the
// locked keys removed, so what you copy is directly editable and directly
// saveable — see wallets/preview.py:build_scaffold.
import { useState } from 'react'
import { ClipboardCopy, FileJson, Loader2 } from 'lucide-react'

const PANES = [
  ['apple', 'Apple pass.json'],
  ['google_class', 'Google class'],
  ['google_object', 'Google object'],
]

export default function ScaffoldPanel({ scaffold, isLoading, hasOverlay, onAdopt }) {
  const [tab, setTab] = useState('apple')

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-card border border-line bg-surface p-4 text-sm text-tx-3">
        <Loader2 size={14} className="animate-spin" /> Reading the current pass…
      </div>
    )
  }
  if (!scaffold) return null

  const body = scaffold[tab]
  const target = tab === 'apple' ? 'apple' : 'google'
  const section = tab === 'google_class' ? 'class' : tab === 'google_object' ? 'object' : null

  return (
    <div className="rounded-card border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <FileJson size={14} className="shrink-0 text-tx-3" />
        <span className="text-sm font-semibold text-tx">Current pass</span>
        <span className="text-[11px] text-tx-3">
          what this card renders now — tokens intact, locked keys removed
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-b border-line px-2 py-1.5">
        {PANES.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded px-2 py-1 text-xs font-semibold ${
              tab === key ? 'bg-brand-bg text-brand' : 'text-tx-3 hover:text-tx-2'
            }`}
          >
            {label}
          </button>
        ))}
        <button
          onClick={() => onAdopt(target, body, section)}
          disabled={!body}
          title={
            hasOverlay
              ? 'Replaces what is currently in the overlay editor'
              : 'Copies this into the overlay editor so you can edit it'
          }
          className="ms-auto flex items-center gap-1.5 rounded border border-line px-2 py-1 text-[11px] font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
        >
          <ClipboardCopy size={12} />
          {hasOverlay ? 'Replace overlay with this' : 'Copy to overlay'}
        </button>
      </div>

      {Object.keys(scaffold.errors || {}).length > 0 && (
        <div className="border-b border-danger/30 bg-danger/10 px-3 py-2">
          {Object.entries(scaffold.errors).map(([key, message]) => (
            <p key={key} className="font-mono text-[11px] text-danger">
              {key}: {message}
            </p>
          ))}
        </div>
      )}

      <pre className="max-h-80 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-tx-2">
        {body ? JSON.stringify(body, null, 2) : '—'}
      </pre>

      {/* The one thing an admin needs to understand before clicking Copy: an
          overlay is a pin, not a snapshot. Whatever it contains stops following
          the Editor, because the overlay is merged last and always wins. */}
      <p className="border-t border-line px-3 py-2 text-[11px] leading-relaxed text-tx-3">
        Copying pins these keys as an overlay — they stop following the Editor, since the overlay is
        merged last and always wins. If you only want to change one field, copy just that field
        instead of the whole document.
      </p>
    </div>
  )
}
