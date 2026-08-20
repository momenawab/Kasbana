import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { useSalesUsers, useUpdateLead } from './api'
import { KIND, optionsFor } from './crm'

// The bulk action bar, shown only when rows are selected.
//
// It fans out one PATCH per lead rather than calling a bulk endpoint, because
// there isn't one — and that is a deliberate trade, not an oversight. Going
// through the normal update path means each lead gets its own timeline entry,
// its own re-score and its own audit record, which is exactly what a reviewer
// needs six months later when asking why forty leads changed hands at once. A
// bulk endpoint would be one request and one audit line for forty leads.
//
// The cost is N requests, so the count is capped: past that, the fan-out is
// slow enough that it deserves a real endpoint rather than a loop with a
// progress bar pretending to be one.
const MAX_BULK = 50

export default function BulkBar({ selected, onClear, choices }) {
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(0)
  const [failed, setFailed] = useState(0)
  const update = useUpdateLead()
  const { data: salesUsers } = useSalesUsers()

  const ids = [...selected]
  const tooMany = ids.length > MAX_BULK

  async function applyToAll(patch) {
    setBusy(true)
    setDone(0)
    setFailed(0)
    // Sequential, not Promise.all: forty parallel writes to the same table is a
    // good way to turn a convenience into an incident, and this is a background
    // chore, not something anyone is watching a spinner for.
    let ok = 0
    let bad = 0
    for (const id of ids) {
      try {
        await update.mutateAsync({ id, ...patch })
        setDone(++ok)
      } catch {
        // One lead failing must not abandon the other thirty-nine — report the
        // count at the end instead.
        setFailed(++bad)
      }
    }
    setBusy(false)
    if (bad === 0) onClear()
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-card border border-brand/40 bg-brand-bg/40 px-4 py-3">
      <span className="text-sm font-semibold text-tx">
        {ids.length} selected
      </span>

      {tooMany ? (
        <span className="text-xs text-warn">
          Select {MAX_BULK} or fewer to apply a bulk change.
        </span>
      ) : busy ? (
        <span className="flex items-center gap-2 text-xs text-tx-2">
          <Loader2 size={13} className="animate-spin" />
          Updating {done + failed} of {ids.length}…
        </span>
      ) : (
        <>
          <select
            defaultValue=""
            onChange={(e) => e.target.value && applyToAll({ status: e.target.value })}
            className={selectClass}
          >
            <option value="">Set status…</option>
            {optionsFor(choices, KIND.STATUS).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </select>

          <select
            defaultValue=""
            onChange={(e) => e.target.value && applyToAll({ priority: e.target.value })}
            className={selectClass}
          >
            <option value="">Set priority…</option>
            {optionsFor(choices, KIND.PRIORITY).map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.label}
              </option>
            ))}
          </select>

          <select
            defaultValue=""
            onChange={(e) =>
              e.target.value &&
              applyToAll({ assigned_sales: e.target.value === '__none__' ? null : e.target.value })
            }
            className={selectClass}
          >
            <option value="">Assign to…</option>
            <option value="__none__">Unassign</option>
            {(salesUsers ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name || a.email}
              </option>
            ))}
          </select>
        </>
      )}

      {failed > 0 && !busy && (
        <span className="text-xs text-danger">
          {failed} of {ids.length} failed — the rest were updated.
        </span>
      )}

      <button
        onClick={onClear}
        className="ml-auto flex items-center gap-1 text-xs text-tx-3 hover:text-tx"
      >
        <X size={13} /> Clear
      </button>
    </div>
  )
}

const selectClass =
  'rounded-ctl border border-line bg-surface px-3 py-1.5 text-xs text-tx focus:border-brand focus:outline-none'
