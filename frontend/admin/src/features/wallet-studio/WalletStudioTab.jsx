// Wallet Studio — build a merchant's wallet card from the admin console.
//
// Left rail lists the merchant's cards; picking one opens two views over the
// same design:
//
//   Editor — the merchant's own WalletDesignEditor, copied verbatim from
//            frontend/dashboard/src/features/cards. What the merchant can do,
//            the platform can do, with the same controls and the same preview.
//   JSON   — the admin-only raw pass overlay, merged over the generated payload.
//            This is the escape hatch to pass features no template exposes
//            (locations, semantics, per-field alignment, …). It opens on the
//            card's CURRENT pass (ScaffoldPanel) rather than an empty document,
//            so a card designed in the Editor can be picked up and edited
//            instead of retyped.
//
// Saving is cheap and does NOT touch live passes. Republish is a separate,
// explicit action, because a card can have tens of thousands of holders and an
// admin iterating on a design should not fire a push per save.
import { useEffect, useMemo, useState } from 'react'
import { Loader2, RefreshCw, Send, Wallet } from 'lucide-react'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import Toaster from '../../components/Toaster'
import { num } from '../../lib/format'
import WalletDesignEditor from './WalletDesignEditor'
import JsonEditor from './JsonEditor'
import OverlayGuide from './OverlayGuide'
import ScaffoldPanel from './ScaffoldPanel'
import {
  useMerchantCards,
  usePassPreview,
  useRepublish,
  usePassScaffold,
  useSaveWalletDesign,
  useWalletDesign,
} from './api'

export default function WalletStudioTab({ merchantId, merchantName }) {
  const { data: cards, isLoading } = useMerchantCards(merchantId)
  const [cardId, setCardId] = useState(null)

  // Default to the first card so the tab is never an empty shell when there is
  // something to show.
  useEffect(() => {
    if (!cardId && cards?.length) setCardId(cards[0].id)
  }, [cards, cardId])

  const card = useMemo(() => cards?.find((c) => c.id === cardId) || null, [cards, cardId])

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-tx-3">
        <Loader2 size={16} className="animate-spin" /> Loading cards…
      </div>
    )
  }

  if (!cards?.length) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center">
        <Wallet size={28} className="mx-auto mb-2 text-tx-3" />
        <h2 className="font-head font-semibold text-tx">No cards yet</h2>
        <p className="mt-1 text-sm text-tx-3">
          {merchantName} hasn’t created a loyalty card. The studio edits an existing card’s pass
          design — the card itself is created from the merchant dashboard.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <Toaster />
      {/* Card rail */}
      <div className="flex shrink-0 flex-col gap-1.5 lg:w-56">
        {cards.map((c) => {
          const active = c.id === cardId
          return (
            <button
              key={c.id}
              onClick={() => setCardId(c.id)}
              className={`rounded-ctl border px-3 py-2 text-left transition ${
                active ? 'border-brand bg-brand-bg/40' : 'border-line hover:border-tx-3'
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-3 w-3 shrink-0 rounded-full border border-line"
                  style={{ background: c.color_bg || '#0E1B2A' }}
                />
                <span className="truncate text-sm font-semibold text-tx">{c.name}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-tx-3">
                <span>{c.type === 'POINTS' ? 'Points' : `${c.stamps_required} stamps`}</span>
                <span>·</span>
                <span>{num(c.customers_count)} holders</span>
                {c.has_overlay && <Badge tone="brand">JSON</Badge>}
              </div>
            </button>
          )
        })}
      </div>

      {card && (
        <CardStudio key={card.id} merchantId={merchantId} merchantName={merchantName} card={card} />
      )}
    </div>
  )
}

function CardStudio({ merchantId, merchantName, card }) {
  const toast = useToast()
  const [view, setView] = useState('editor')
  const { data: saved } = useWalletDesign(merchantId, card.id)
  const { data: scaffold, isLoading: scaffoldLoading } = usePassScaffold(merchantId, card.id)
  const save = useSaveWalletDesign(merchantId, card.id)
  const preview = usePassPreview(merchantId, card.id)
  const republish = useRepublish(merchantId, card.id)

  // Overlay state is owned here, not by the copied editor — the editor knows
  // nothing about overlays, and keeping them out of it is what lets it stay a
  // verbatim copy of the merchant's.
  const [apple, setApple] = useState({})
  const [google, setGoogle] = useState({})
  const [appleOk, setAppleOk] = useState(true)
  const [googleOk, setGoogleOk] = useState(true)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (!saved) return
    setApple(saved.apple_overlay || {})
    setGoogle(saved.google_overlay || {})
    setDirty(false)
  }, [saved])

  const onApple = (value, ok) => {
    setAppleOk(ok)
    if (ok && value) {
      setApple(value)
      setDirty(true)
    }
  }
  const onGoogle = (value, ok) => {
    setGoogleOk(ok)
    if (ok && value) {
      setGoogle(value)
      setDirty(true)
    }
  }

  const insert = (json) => {
    setApple((current) => ({ ...current, ...json }))
    setDirty(true)
  }

  // Adopt the generated pass into the overlay. Google arrives as one half at a
  // time (class or object), so it merges into its own section rather than
  // replacing the whole document and wiping the other half.
  const adopt = (target, body, section) => {
    if (!body) return
    if (target === 'apple') {
      setApple(body)
    } else {
      setGoogle((current) => ({ ...current, [section]: body }))
    }
    setDirty(true)
    toast.success('Copied into the overlay. Review it, then Save.')
  }

  const saveOverlays = () => {
    save.mutate(
      { apple_overlay: apple, google_overlay: google },
      {
        onSuccess: () => {
          setDirty(false)
          toast.success('Pass JSON saved. Use Republish to push it to live passes.')
        },
        onError: (err) => toast.error(normalizeError(err).message),
      }
    )
  }

  const runPreview = () => {
    preview.mutate(
      { design: { apple_overlay: apple, google_overlay: google } },
      { onError: (err) => toast.error(normalizeError(err).message) }
    )
  }

  const doRepublish = () => {
    const holders = card.customers_count || 0
    const ok = window.confirm(
      `Push this design to ${holders} live pass${holders === 1 ? '' : 'es'} on “${card.name}”?\n\n` +
        'Every holder’s wallet updates. This cannot be undone from here.'
    )
    if (!ok) return
    republish.mutate(undefined, {
      onSuccess: (data) => toast.success(`Queued ${data.customer_cards} pass update(s).`),
      onError: (err) => toast.error(normalizeError(err).message),
    })
  }

  const canSave = appleOk && googleOk && dirty && !save.isPending

  return (
    <div className="min-w-0 flex-1">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line">
        <div className="flex gap-1">
          {[
            ['editor', 'Editor'],
            ['json', 'Pass JSON'],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`relative px-3 py-2 text-sm ${
                view === key ? 'text-brand' : 'text-tx-3 hover:text-tx-2'
              }`}
            >
              {label}
              {view === key && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-brand" />}
            </button>
          ))}
        </div>
        <button
          onClick={doRepublish}
          disabled={republish.isPending}
          title="Push the saved design to every live pass on this card"
          className="mb-1 flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
        >
          {republish.isPending ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Send size={14} />
          )}
          Republish ({num(card.customers_count)})
        </button>
      </div>

      {view === 'editor' ? (
        <WalletDesignEditor
          merchantId={merchantId}
          cardId={card.id}
          card={{ ...card, merchantName }}
        />
      ) : (
        <div className="flex flex-col gap-4 xl:flex-row">
          <div className="flex min-w-0 flex-1 flex-col gap-4">
            <ScaffoldPanel
              scaffold={scaffold}
              isLoading={scaffoldLoading}
              hasOverlay={Object.keys(apple).length > 0 || Object.keys(google).length > 0}
              onAdopt={adopt}
            />
            <JsonEditor
              label="Apple — pass.json overlay"
              hint="Merged over the generated pass.json. Anything PassKit accepts on a storeCard."
              value={apple}
              onChange={onApple}
            />
            <JsonEditor
              label="Google — class / object overlay"
              hint='Two halves: {"class": {…}, "object": {…}}.'
              value={google}
              onChange={onGoogle}
              rows={10}
            />

            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={saveOverlays}
                disabled={!canSave}
                className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
              >
                {save.isPending && <Loader2 size={14} className="animate-spin" />}
                Save pass JSON
              </button>
              <button
                onClick={runPreview}
                disabled={!appleOk || !googleOk || preview.isPending}
                className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
              >
                {preview.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RefreshCw size={14} />
                )}
                Preview resolved pass
              </button>
              {dirty && <span className="text-xs text-warn">Unsaved changes</span>}
            </div>

            {preview.data && <PreviewResult data={preview.data} />}
          </div>

          <div className="w-full shrink-0 xl:w-96">
            <OverlayGuide onInsert={insert} />
          </div>
        </div>
      )}
    </div>
  )
}

// The resolved payloads, exactly as the phone will receive them — tokens already
// substituted for a sample customer. This is the thing worth reading before a
// republish: it is the merge result, not what was typed.
function PreviewResult({ data }) {
  const [tab, setTab] = useState('apple')
  const panes = [
    ['apple', 'Apple pass.json', data.apple],
    ['google_class', 'Google class', data.google_class],
    ['google_object', 'Google object', data.google_object],
  ]
  const active = panes.find(([key]) => key === tab)

  return (
    <div className="rounded-card border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-1 border-b border-line px-2 py-1.5">
        {panes.map(([key, label]) => (
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
        <span className="ml-auto pe-1 text-[11px] text-tx-3">
          sample: {data.stamp_count}/{data.stamps_required} stamps
        </span>
      </div>
      {Object.keys(data.errors || {}).length > 0 && (
        <div className="border-b border-danger/30 bg-danger/10 px-3 py-2">
          {Object.entries(data.errors).map(([key, message]) => (
            <p key={key} className="font-mono text-[11px] text-danger">
              {key}: {message}
            </p>
          ))}
        </div>
      )}
      <pre className="max-h-96 overflow-auto p-3 font-mono text-[11px] leading-relaxed text-tx-2">
        {active?.[2] ? JSON.stringify(active[2], null, 2) : '—'}
      </pre>
    </div>
  )
}
