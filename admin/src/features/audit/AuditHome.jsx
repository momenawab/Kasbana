import { useState } from 'react'
import { Loader2, Download, Search, X } from 'lucide-react'
import { useAudit, downloadAuditCsv } from './api'

const EMPTY = { actor: '', action: '', target_type: '', from: '', to: '' }

function fmt(ts) {
  return ts ? new Date(ts).toLocaleString() : '—'
}

export default function AuditHome() {
  const [draft, setDraft] = useState(EMPTY)
  const [filters, setFilters] = useState(EMPTY)
  const [selected, setSelected] = useState(null)
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useAudit(filters)

  const rows = data?.pages.flatMap((p) => p.results) ?? []
  const set = (k) => (e) => setDraft((d) => ({ ...d, [k]: e.target.value }))

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">Audit Log</h1>
        <button
          onClick={() => downloadAuditCsv(filters)}
          className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand"
        >
          <Download size={15} /> Export CSV
        </button>
      </div>
      <p className="text-sm text-tx-3">
        Every mutating admin action, append-only. Filter by actor, action, or target; open a row for
        the full before/after detail.
      </p>

      {/* Filters */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setFilters(draft)
        }}
        className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-4"
      >
        <Field
          label="Actor email"
          value={draft.actor}
          onChange={set('actor')}
          placeholder="jane@"
        />
        <Field
          label="Action"
          value={draft.action}
          onChange={set('action')}
          placeholder="merchant.suspend"
        />
        <Field
          label="Target type"
          value={draft.target_type}
          onChange={set('target_type')}
          placeholder="merchant"
        />
        <Field label="From" type="date" value={draft.from} onChange={set('from')} />
        <Field label="To" type="date" value={draft.to} onChange={set('to')} />
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white"
        >
          <Search size={15} /> Filter
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft(EMPTY)
            setFilters(EMPTY)
          }}
          className="rounded-ctl px-3 py-2 text-sm text-tx-3 hover:text-tx"
        >
          Reset
        </button>
      </form>

      {/* Table */}
      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Actor</th>
                <th className="px-4 py-3 font-medium">Action</th>
                <th className="px-4 py-3 font-medium">Target</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-tx-3">
                    No matching events.
                  </td>
                </tr>
              )}
              {rows.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2"
                >
                  <td className="whitespace-nowrap px-4 py-2.5 text-tx-3">{fmt(e.created_at)}</td>
                  <td className="px-4 py-2.5 text-tx-2">{e.actor_email || '—'}</td>
                  <td className="px-4 py-2.5 font-num text-tx">{e.action}</td>
                  <td className="px-4 py-2.5 text-tx-3">
                    {e.target_type ? `${e.target_type} · ${e.target_id}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="mx-auto rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
        >
          {isFetchingNextPage ? 'Loading…' : 'Load more'}
        </button>
      )}

      {selected && <DetailDrawer event={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function Field({ label, ...props }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      {label}
      <input
        {...props}
        className="w-44 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none"
      />
    </label>
  )
}

function DetailDrawer({ event, onClose }) {
  const { before, after, ...rest } = event.metadata || {}
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-md flex-col gap-4 overflow-y-auto border-l border-line bg-surface p-5"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="font-num text-lg text-tx">{event.action}</div>
            <div className="text-sm text-tx-3">{fmt(event.created_at)}</div>
          </div>
          <button onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        <dl className="flex flex-col gap-2 border-y border-line py-3 text-sm">
          <Row label="Actor" value={event.actor_email || '—'} />
          <Row
            label="Target"
            value={event.target_type ? `${event.target_type} · ${event.target_id}` : '—'}
          />
          <Row label="IP" value={event.ip || '—'} />
        </dl>

        {(before || after) && (
          <div className="grid grid-cols-2 gap-3">
            <Json title="Before" value={before} />
            <Json title="After" value={after} />
          </div>
        )}
        {Object.keys(rest).length > 0 && <Json title="Details" value={rest} />}
        {event.user_agent && (
          <div className="text-xs text-tx-3">
            <div className="mb-1 font-semibold">User agent</div>
            {event.user_agent}
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-tx-3">{label}</dt>
      <dd className="text-right text-tx">{value}</dd>
    </div>
  )
}

function Json({ title, value }) {
  return (
    <div>
      <div className="mb-1 text-xs font-semibold text-tx-3">{title}</div>
      <pre className="overflow-x-auto rounded-ctl border border-line bg-bg p-2 text-xs text-tx-2">
        {value ? JSON.stringify(value, null, 2) : '—'}
      </pre>
    </div>
  )
}
