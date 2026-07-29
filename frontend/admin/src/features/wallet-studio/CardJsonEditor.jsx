// Edit the entire card as one JSON document.
//
// The narrow "overlay only" editor answered "change a pass key"; this answers
// "change anything about this card" — the program (name, goal, reward, colours,
// image URLs), how it renders (template, stamp style, sizes, strip artwork) and
// the raw pass payload, in one place.
//
// Two blocks are read-only and shown *beside* the editor rather than inside it:
// the platform-managed identity keys, and the image slots. Both are part of the
// card and both would be misleading to present as editable — the keys because
// writing them breaks live passes, the images because pixels are not JSON (their
// source URLs, which are editable, live under card/design in the document).
import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, Loader2, RotateCcw, Save } from 'lucide-react'
import { normalizeError } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import { useCardJson, useSaveCardJson } from './api'

// Sections the admin may write. `platform` and `assets` come back on every read
// but are stripped before saving — the server ignores them either way, and
// leaving them in the editable document invites someone to try editing them.
const WRITABLE = ['card', 'design', 'apple_overlay', 'google_overlay']

// Card fields that change the deal for people already holding the card. Mirrors
// console/card_json.py:HOLDER_AFFECTING.
const HOLDER_AFFECTING = ['type', 'stamps_required', 'single_use']

function writableOnly(document) {
  if (!document) return null
  const out = {}
  for (const key of WRITABLE) if (document[key] !== undefined) out[key] = document[key]
  return out
}

export default function CardJsonEditor({ merchantId, card, injection }) {
  const toast = useToast()
  const { data: document, isLoading } = useCardJson(merchantId, card.id)
  const save = useSaveCardJson(merchantId, card.id)

  const [text, setText] = useState('')
  const [touched, setTouched] = useState(false)

  const serverText = useMemo(() => {
    const w = writableOnly(document)
    return w ? JSON.stringify(w, null, 2) : ''
  }, [document])

  // Seed once, and re-seed after a save — but never clobber an in-progress edit.
  useEffect(() => {
    if (!serverText) return
    setText((current) => (touched && current ? current : serverText))
  }, [serverText, touched])

  // Copy-to-overlay (scaffold panel) and snippet inserts (guide) both arrive as
  // an injection carrying a nonce, so repeating the same insert still fires. They
  // edit the document here rather than owning their own state, which is what
  // keeps this component the single source of truth for what will be saved.
  useEffect(() => {
    if (!injection?.nonce) return
    setText((current) => {
      let doc
      try {
        doc = JSON.parse(current || '{}')
      } catch {
        toast.error('Fix the JSON before inserting — the document could not be parsed.')
        return current
      }
      const { section, value, merge } = injection
      if (section === 'apple_overlay') {
        doc.apple_overlay = merge ? { ...(doc.apple_overlay || {}), ...value } : value
      } else {
        // Google arrives one half at a time, so it must not wipe the other.
        doc.google_overlay = { ...(doc.google_overlay || {}), [injection.half]: value }
      }
      return JSON.stringify(doc, null, 2)
    })
    setTouched(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [injection?.nonce])

  const parsed = useMemo(() => {
    const trimmed = text.trim()
    if (!trimmed) return { ok: false, error: 'Document is empty.' }
    try {
      const value = JSON.parse(trimmed)
      if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return { ok: false, error: 'Must be a JSON object.' }
      }
      return { ok: true, value }
    } catch (err) {
      return { ok: false, error: err.message }
    }
  }, [text])

  // Warn when an edit moves the goalposts for existing holders.
  const risky = useMemo(() => {
    if (!parsed.ok || !document?.card) return []
    const next = parsed.value.card || {}
    return HOLDER_AFFECTING.filter(
      (field) => next[field] !== undefined && next[field] !== document.card[field]
    )
  }, [parsed, document])

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-tx-3">
        <Loader2 size={16} className="animate-spin" /> Loading the card…
      </div>
    )
  }

  const onSave = () => {
    if (!parsed.ok) return
    if (risky.length) {
      const holders = card.customers_count || 0
      const ok = window.confirm(
        `You are changing ${risky.join(', ')} on “${card.name}”.\n\n` +
          `This changes the deal for ${holders} existing holder${holders === 1 ? '' : 's'}. Continue?`
      )
      if (!ok) return
    }
    save.mutate(parsed.value, {
      onSuccess: () => {
        setTouched(false)
        toast.success('Card saved. Use Republish to push it to live passes.')
      },
      onError: (err) => {
        const { message, fields } = normalizeError(err)
        const detail = fields && Object.keys(fields).length ? JSON.stringify(fields) : ''
        toast.error(detail ? `${message} — ${detail}` : message)
      },
    })
  }

  const revert = () => {
    setText(serverText)
    setTouched(false)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-tx">Card JSON</h3>
          <p className="text-xs text-tx-3">
            Everything about this card — program, design, sizes and raw pass payload.
          </p>
        </div>
        {parsed.ok ? (
          <span className="flex shrink-0 items-center gap-1 text-xs text-success">
            <Check size={12} /> valid
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-1 text-xs text-danger">
            <AlertTriangle size={12} /> invalid
          </span>
        )}
      </div>

      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setTouched(true)
        }}
        rows={34}
        spellCheck={false}
        className={`w-full rounded-ctl border bg-bg p-3 font-mono text-xs leading-relaxed text-tx outline-none focus:border-brand ${
          parsed.ok ? 'border-line' : 'border-danger'
        }`}
      />
      {!parsed.ok && <p className="text-xs text-danger">{parsed.error}</p>}

      {risky.length > 0 && (
        <p className="flex items-start gap-1.5 rounded-ctl border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-warn">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>
            Changing <strong>{risky.join(', ')}</strong> alters the deal for people who already hold
            this card.
          </span>
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onSave}
          disabled={!parsed.ok || !touched || save.isPending}
          className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
        >
          {save.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          Save card
        </button>
        <button
          onClick={revert}
          disabled={!touched}
          className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
        >
          <RotateCcw size={14} /> Revert
        </button>
        {touched && <span className="text-xs text-warn">Unsaved changes</span>}
      </div>

      <ReadOnlyBlocks document={document} />
    </div>
  )
}

function ReadOnlyBlocks({ document }) {
  if (!document) return null
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-card border border-line bg-surface">
        <div className="border-b border-line px-3 py-2">
          <p className="text-sm font-semibold text-tx">Platform-managed keys</p>
          <p className="text-[11px] text-tx-3">
            Part of every pass, but not yours to set — these decide whether a pass can update over
            APNs and whether its QR resolves at the till.
          </p>
        </div>
        <pre className="max-h-64 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-tx-3">
          {JSON.stringify(document.platform || {}, null, 2)}
        </pre>
      </div>

      <div className="rounded-card border border-line bg-surface">
        <div className="border-b border-line px-3 py-2">
          <p className="text-sm font-semibold text-tx">Images in the pass</p>
          <p className="text-[11px] text-tx-3">
            Separate files in the .pkpass, so they never appear in the JSON. Change the source field
            in the document above to change the image.
          </p>
        </div>
        <div className="divide-y divide-line">
          {(document.assets || []).map((asset) => (
            <div key={asset.file} className="flex items-start gap-3 px-3 py-2">
              {asset.url ? (
                <img src={asset.url} alt="" className="h-10 w-10 shrink-0 rounded object-contain" />
              ) : (
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-surface-2 text-[10px] text-tx-3">
                  none
                </span>
              )}
              <div className="min-w-0">
                <p className="font-mono text-xs text-tx-2">
                  {asset.file} <span className="text-tx-3">· {asset.size}</span>
                </p>
                <p className="text-[11px] text-tx-3">{asset.note}</p>
                <p className="mt-0.5 font-mono text-[11px] text-brand">{asset.source_field}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
