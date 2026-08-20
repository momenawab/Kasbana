import { useState } from 'react'
import { AlertTriangle, GitMerge, Loader2, X } from 'lucide-react'
import { useLeadDuplicates, useMergeLead } from './api'
import { normalizeError } from '../../lib/api'
import Badge from '../../components/Badge'

// Merge duplicates into this lead.
//
// The lead on screen is always the survivor — you merge *into* the record you
// are keeping. That framing is the safety: the survivor's status, priority and
// already-filled fields are never touched, so nobody accidentally drags a
// qualified lead back to New by merging the wrong way. The absorbed lead only
// fills gaps and hands over its calls and timeline.
export default function MergeModal({ lead, onClose, onMerged }) {
  const { data: duplicates, isLoading } = useLeadDuplicates(lead.id)
  const merge = useMergeLead()
  const [chosen, setChosen] = useState(null)
  const [err, setErr] = useState('')

  const candidates = (duplicates ?? []).filter((d) => !d.is_converted)
  const converted = (duplicates ?? []).filter((d) => d.is_converted)

  async function submit() {
    if (!chosen) return
    setErr('')
    try {
      await merge.mutateAsync({ survivorId: lead.id, absorbedId: chosen })
      onMerged?.()
      onClose()
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-1 flex items-start justify-between">
          <div className="flex items-center gap-2 text-tx">
            <GitMerge size={17} className="text-brand" />
            <h2 className="font-head font-semibold">Merge duplicates</h2>
          </div>
          <button onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 text-xs text-tx-3">
          The chosen lead is folded into <b className="text-tx-2">{lead.business_name}</b> and
          deleted. This lead’s status and filled-in details are kept; only its blanks are filled,
          and the other lead’s calls and history move across.
        </p>

        {isLoading ? (
          <Loader2 className="mx-auto my-8 animate-spin text-tx-3" />
        ) : candidates.length === 0 && converted.length === 0 ? (
          <div className="rounded-ctl border border-line bg-bg p-6 text-center text-sm text-tx-3">
            No duplicates found for this lead.
          </div>
        ) : (
          <div className="flex max-h-72 flex-col gap-2 overflow-y-auto">
            {candidates.map((d) => (
              <label
                key={d.id}
                className={`flex cursor-pointer items-start gap-3 rounded-ctl border p-3 transition ${
                  chosen === d.id ? 'border-brand bg-brand-bg/30' : 'border-line hover:border-brand/50'
                }`}
              >
                <input
                  type="radio"
                  name="absorbed"
                  checked={chosen === d.id}
                  onChange={() => setChosen(d.id)}
                  className="mt-1 accent-brand"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-tx">{d.business_name}</span>
                    <Badge tone="neutral">{d.lead_type}</Badge>
                  </div>
                  <div className="mt-0.5 font-num text-xs text-tx-3">
                    {d.phone}
                    {d.email && ` · ${d.email}`}
                  </div>
                  <div className="mt-0.5 text-xs text-tx-3">
                    {d.name || 'No owner'} ·{' '}
                    {d.assigned_sales?.name || d.assigned_sales?.email || 'Unassigned'}
                  </div>
                </div>
              </label>
            ))}

            {/* A converted duplicate can't be absorbed — merging that direction
                would strand the merchant. Shown, not hidden, so the person
                understands why they can't pick it. */}
            {converted.map((d) => (
              <div
                key={d.id}
                className="flex items-start gap-2 rounded-ctl border border-line bg-bg p-3 opacity-70"
              >
                <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-tx">{d.business_name}</span>
                    <Badge tone="success">Converted</Badge>
                  </div>
                  <div className="mt-0.5 text-xs text-tx-3">
                    Already a merchant — merge this lead into it from its own page instead.
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {err && <div className="mt-3 text-sm text-danger">{err}</div>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!chosen || merge.isPending}
            className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
          >
            {merge.isPending ? <Loader2 size={14} className="animate-spin" /> : <GitMerge size={14} />}
            Merge in
          </button>
        </div>
      </div>
    </div>
  )
}
