import { useEffect, useState } from 'react'
import { Loader2, Plus, RotateCcw, Trophy } from 'lucide-react'
import { useResetDemoCard, useStampDemoCard } from './api'
import { normalizeError } from '../../lib/api'

// The live stamp control, used while pitching: tap "+1" and the prospect's
// wallet pass updates on their phone. Mirrors the merchant till's stamping, with
// a quantity so a rep can jump the card to "one away" or straight to the reward.
export default function Stamper({ cardId, initialCount = 0, stampsRequired = 8 }) {
  const [count, setCount] = useState(initialCount)
  const [delta, setDelta] = useState(1)
  const [err, setErr] = useState('')

  const stamp = useStampDemoCard(cardId)
  const reset = useResetDemoCard(cardId)
  const busy = stamp.isPending || reset.isPending

  // Reopening a different card must not show the previous card's balance.
  useEffect(() => setCount(initialCount), [cardId, initialCount])

  const rewardReady = count >= stampsRequired
  const shown = Math.min(stampsRequired, 12)

  async function run(fn) {
    setErr('')
    try {
      const res = await fn()
      setCount(res.stamp_count)
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-bg p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold text-tx">Stamp it live</span>
        <span className="font-num text-sm text-tx-2">
          {count} / {stampsRequired}
        </span>
      </div>

      {/* Balance at a glance — the thing the prospect is watching change. */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {Array.from({ length: shown }).map((_, i) => (
          <span
            key={i}
            className={
              'h-5 w-5 rounded-full border ' +
              (i < Math.min(count, shown)
                ? 'border-brand bg-brand'
                : 'border-line bg-transparent')
            }
          />
        ))}
      </div>

      {rewardReady && (
        <div className="mb-3 flex items-center gap-1.5 rounded-ctl border border-success/40 bg-success/10 px-3 py-2 text-xs text-success">
          <Trophy size={13} /> Reward unlocked
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="number"
          min={1}
          max={30}
          value={delta}
          onChange={(e) => setDelta(e.target.value)}
          aria-label="Stamps to add"
          className="w-16 rounded-ctl border border-line bg-bg px-2 py-1.5 text-center font-num text-sm text-tx focus:border-brand focus:outline-none"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => stamp.mutateAsync(Number(delta) || 1))}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
        >
          {stamp.isPending ? <Loader2 size={14} className="animate-spin" /> : <Plus size={15} />}
          Add {Number(delta) || 1} stamp{(Number(delta) || 1) > 1 ? 's' : ''}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => reset.mutateAsync())}
          title="Reset to zero"
          className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-50"
        >
          <RotateCcw size={14} />
        </button>
      </div>

      {err && <div className="mt-2 text-xs text-danger">{err}</div>}
      <p className="mt-2 text-[11px] text-tx-3">
        Updates the pass on the phone that added it.
      </p>
    </div>
  )
}
