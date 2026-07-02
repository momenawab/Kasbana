import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, AlertTriangle, ShieldAlert, Check, X, ScanLine } from 'lucide-react'
import { usePipeline, useAtRisk, useModerationQueue, useRunScan, useResolveFlag } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, fromNow } from '../../lib/format'

const SUPPORT_ROLES = ['SUPER_ADMIN', 'SUPPORT']

const TABS = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'atrisk', label: 'At-risk' },
  { key: 'moderation', label: 'Moderation' },
]

const STAGE_TONE = { lead: 'neutral', trial: 'info', active: 'success', churned: 'danger' }

export default function LifecycleHome() {
  const [tab, setTab] = useState('pipeline')

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Lifecycle &amp; Moderation</h1>
      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={
              'relative px-3 py-2 text-sm ' +
              (tab === t.key ? 'text-brand' : 'text-tx-3 hover:text-tx-2')
            }
          >
            {t.label}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-brand" />}
          </button>
        ))}
      </div>
      {tab === 'pipeline' && <Pipeline />}
      {tab === 'atrisk' && <AtRisk />}
      {tab === 'moderation' && <Moderation />}
    </div>
  )
}

function Pipeline() {
  const { data, isLoading } = usePipeline()
  if (isLoading) return <Loader2 className="mx-auto mt-8 animate-spin text-tx-3" />
  const stages = data?.stages ?? []
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {stages.map((s) => (
        <div key={s.stage} className="rounded-card border border-line bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <Badge tone={STAGE_TONE[s.stage] || 'neutral'}>{s.stage}</Badge>
            <span className="font-num text-xl text-tx">{num(s.count)}</span>
          </div>
          <ul className="flex flex-col gap-1">
            {s.merchants.map((m) => (
              <li key={m.id}>
                <Link to={`/merchants/${m.id}`} className="text-sm text-tx-2 hover:text-brand">
                  {m.name}
                </Link>
              </li>
            ))}
            {s.count > s.merchants.length && (
              <li className="text-xs text-tx-3">+{s.count - s.merchants.length} more</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  )
}

function AtRisk() {
  const { data, isLoading } = useAtRisk()
  if (isLoading) return <Loader2 className="mx-auto mt-8 animate-spin text-tx-3" />
  const rows = data ?? []
  if (rows.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
        No at-risk merchants right now.
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="border-b border-line text-tx-3">
          <tr className="text-left">
            <th className="px-4 py-3 font-medium">Merchant</th>
            <th className="px-4 py-3 font-medium">Health</th>
            <th className="px-4 py-3 font-medium">Reasons</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line/60 last:border-0">
              <td className="px-4 py-3">
                <Link to={`/merchants/${r.id}`} className="text-brand hover:underline">
                  {r.name}
                </Link>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-2">
                  <AlertTriangle
                    size={14}
                    className={r.health_score < 40 ? 'text-danger' : 'text-warn'}
                  />
                  <span className="font-num text-tx">{r.health_score}</span>
                </span>
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap gap-1">
                  {r.reasons.map((reason) => (
                    <Badge key={reason} tone="warn">
                      {reason}
                    </Badge>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Moderation() {
  const { role } = useAuth()
  const canAct = SUPPORT_ROLES.includes(role)
  const { data, isLoading } = useModerationQueue('pending')
  const scan = useRunScan()
  const resolve = useResolveFlag()
  const [msg, setMsg] = useState(null)

  const rows = data ?? []

  async function runScan() {
    setMsg(null)
    try {
      const r = await scan.mutateAsync()
      setMsg(`Scan complete — ${r.created} new flag(s) from ${r.scanned_cards} cards.`)
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  async function act(id, action) {
    try {
      await resolve.mutateAsync({ id, action })
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-tx-3">Flagged content awaiting review.</p>
        {canAct && (
          <button
            onClick={runScan}
            disabled={scan.isPending}
            className="flex items-center gap-2 rounded-ctl border border-line bg-surface-2 px-3 py-1.5 text-sm font-semibold text-tx hover:border-brand disabled:opacity-60"
          >
            <ScanLine size={15} /> {scan.isPending ? 'Scanning…' : 'Run scan'}
          </button>
        )}
      </div>
      {msg && <p className="text-sm text-tx-2">{msg}</p>}

      {isLoading ? (
        <Loader2 className="mx-auto mt-4 animate-spin text-tx-3" />
      ) : rows.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
          <ShieldAlert size={22} className="mx-auto mb-2" />
          Nothing flagged. The queue is clear.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((f) => (
            <div
              key={f.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface p-4"
            >
              <div>
                <div className="flex items-center gap-2">
                  <Badge tone="warn">{f.target_type}</Badge>
                  <span className="text-tx">{f.label || f.target_id}</span>
                </div>
                <div className="mt-1 text-xs text-tx-3">
                  {f.reason} · {f.source} ·{' '}
                  <Link to={`/merchants/${f.merchant.id}`} className="text-brand hover:underline">
                    {f.merchant.name}
                  </Link>{' '}
                  · {fromNow(f.created_at)}
                </div>
              </div>
              {canAct && (
                <div className="flex gap-2">
                  <button
                    onClick={() => act(f.id, 'approve')}
                    disabled={resolve.isPending}
                    className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-success hover:text-success disabled:opacity-60"
                  >
                    <Check size={14} /> Approve
                  </button>
                  <button
                    onClick={() => act(f.id, 'reject')}
                    disabled={resolve.isPending}
                    className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-danger hover:text-danger disabled:opacity-60"
                  >
                    <X size={14} /> Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
