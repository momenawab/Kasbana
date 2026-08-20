import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import Badge from '../../components/Badge'
import { useAiQueue, useVerificationQueue } from './api'

const TASK_TONES = {
  queued: 'neutral',
  running: 'info',
  completed: 'success',
  failed: 'danger',
  skipped: 'neutral',
}

const RESULT_TONES = {
  verified: 'success',
  possible: 'warn',
  invalid: 'danger',
  unknown: 'neutral',
}

const TABS = [
  { key: 'ai', label: 'AI enrichment' },
  { key: 'verification', label: 'Verification' },
]

export default function QueuesHome() {
  const [tab, setTab] = useState('ai')
  const [status, setStatus] = useState('')

  return (
    <div className="space-y-5">
      <Link
        to="/leadgen"
        className="inline-flex items-center gap-1.5 text-sm text-tx-2 hover:text-tx"
      >
        <ArrowLeft size={14} /> Searches
      </Link>
      <header>
        <h1 className="text-xl font-semibold text-tx">Queues</h1>
        <p className="mt-1 text-sm text-tx-2">
          Paid work in flight. Both drain in the background — you can leave this page.
        </p>
      </header>

      <nav className="flex gap-1 border-b border-surface-2">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            onClick={() => setTab(entry.key)}
            className={
              'px-3 py-2 text-sm transition ' +
              (tab === entry.key
                ? 'border-b-2 border-brand font-semibold text-tx'
                : 'text-tx-2 hover:text-tx')
            }
          >
            {entry.label}
          </button>
        ))}
      </nav>

      {tab === 'ai' ? (
        <AiQueue status={status} setStatus={setStatus} />
      ) : (
        <VerificationQueue status={status} setStatus={setStatus} />
      )}
    </div>
  )
}

function StatsRow({ stats, active, onPick }) {
  if (!stats) return null
  return (
    <div className="flex flex-wrap gap-2">
      <Chip on={active === ''} onClick={() => onPick('')}>
        All
      </Chip>
      {Object.entries(stats).map(([key, value]) => (
        <Chip key={key} on={active === key} onClick={() => onPick(key)}>
          {key} <span className="ml-1 opacity-70">{value}</span>
        </Chip>
      ))}
    </div>
  )
}

function AiQueue({ status, setStatus }) {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useAiQueue({
    status,
  })
  const rows = data?.pages.flatMap((p) => p.results ?? []) ?? []
  const stats = data?.pages?.[0]?.stats

  return (
    <div className="space-y-4">
      <StatsRow stats={stats} active={status} onPick={setStatus} />
      {isLoading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <Empty>Nothing here yet. Run AI enrichment from a search to fill this queue.</Empty>
      ) : (
        <Table
          head={['Business', 'Status', 'Tokens', 'Cost', 'Took', 'Confidence']}
          rows={rows.map((row) => [
            <div key="b">
              <p className="text-tx">{row.business_name}</p>
              {row.error && <p className="text-xs text-danger">{row.error}</p>}
            </div>,
            <Badge key="s" tone={TASK_TONES[row.status]}>
              {row.status}
              {row.attempts > 1 ? ` ·${row.attempts}` : ''}
            </Badge>,
            `${row.tokens_in} / ${row.tokens_out}`,
            `$${Number(row.cost_usd).toFixed(4)}`,
            row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '—',
            row.confidence != null ? `${row.confidence}%` : '—',
          ])}
        />
      )}
      <More has={hasNextPage} busy={isFetchingNextPage} onClick={fetchNextPage} />
    </div>
  )
}

function VerificationQueue({ status, setStatus }) {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useVerificationQueue({ status })
  const rows = data?.pages.flatMap((p) => p.results ?? []) ?? []
  const stats = data?.pages?.[0]?.stats

  return (
    <div className="space-y-4">
      <StatsRow stats={stats} active={status} onPick={setStatus} />
      {isLoading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <Empty>Nothing verified yet.</Empty>
      ) : (
        <Table
          head={['Business', 'Contact', 'Result', 'Detail', 'Provider', 'Credits']}
          rows={rows.map((row) => [
            <span key="b" className="text-tx">
              {row.business_name}
            </span>,
            <span key="t" className="text-tx-2">
              {row.target}
            </span>,
            <Badge key="r" tone={RESULT_TONES[row.result] || 'neutral'}>
              {row.result || row.status}
            </Badge>,
            <span key="d" className="text-xs text-tx-2">
              {row.kind === 'phone'
                ? [row.line_type_display, row.carrier].filter(Boolean).join(' · ') || '—'
                : [
                    row.is_role_address ? 'role address' : null,
                    row.is_disposable ? 'disposable' : null,
                    row.domain_valid === false ? 'dead domain' : null,
                  ]
                    .filter(Boolean)
                    .join(' · ') || '—'}
            </span>,
            // An empty provider means the offline fallback ran — worth showing,
            // because it is why the result says "possible" rather than "verified".
            <span key="p" className="text-xs text-tx-2">
              {row.provider || 'offline check'}
            </span>,
            row.credits_used || 0,
          ])}
        />
      )}
      <More has={hasNextPage} busy={isFetchingNextPage} onClick={fetchNextPage} />
    </div>
  )
}

function Table({ head, rows }) {
  return (
    <div className="overflow-x-auto rounded-card bg-surface">
      <table className="w-full text-sm">
        <thead className="border-b border-surface-2 text-left text-xs uppercase tracking-wide text-tx-2">
          <tr>
            {head.map((cell) => (
              <th key={cell} className="p-3">
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, index) => (
            <tr key={index} className="border-b border-surface-2/50 last:border-0">
              {cells.map((cell, cellIndex) => (
                <td key={cellIndex} className="p-3 text-tx-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Chip({ on, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={
        'rounded-full px-3 py-1 text-xs font-semibold capitalize transition ' +
        (on ? 'bg-brand text-white' : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
      }
    >
      {children}
    </button>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center py-16 text-tx-2">
      <Loader2 className="animate-spin" />
    </div>
  )
}

function Empty({ children }) {
  return <p className="rounded-card bg-surface p-10 text-center text-sm text-tx-2">{children}</p>
}

function More({ has, busy, onClick }) {
  if (!has) return null
  return (
    <div className="flex justify-center">
      <button
        onClick={() => onClick()}
        disabled={busy}
        className="rounded-ctl bg-surface-2 px-4 py-2 text-sm text-tx-2 hover:bg-surface-3 hover:text-tx disabled:opacity-50"
      >
        {busy ? 'Loading…' : 'Load more'}
      </button>
    </div>
  )
}
