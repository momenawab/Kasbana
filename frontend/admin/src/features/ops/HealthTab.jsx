import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { useHealth } from './api'

function Dot({ ok }) {
  return ok ? (
    <CheckCircle2 size={18} className="text-success" />
  ) : (
    <XCircle size={18} className="text-danger" />
  )
}

function Tile({ title, ok, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-tx">{title}</span>
        <Dot ok={ok} />
      </div>
      {children && <div className="mt-2 text-xs text-tx-3">{children}</div>}
    </div>
  )
}

export default function HealthTab() {
  const { data, isLoading } = useHealth()
  if (isLoading || !data) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  const queues = data.queues || {}
  const queueErr = queues.error

  return (
    <div className="flex flex-col gap-4">
      <div
        className={
          'rounded-card border p-4 text-sm font-semibold ' +
          (data.healthy
            ? 'border-success/40 bg-surface text-success'
            : 'border-danger/40 bg-surface text-danger')
        }
      >
        {data.healthy ? 'All core systems operational' : 'Degraded — a core dependency is down'}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Tile title="API" ok={data.api?.ok} />
        <Tile title="Database" ok={data.database?.ok}>
          {data.database?.detail}
        </Tile>
        <Tile title="Cache" ok={data.cache?.ok}>
          {data.cache?.backend}
        </Tile>
        <Tile title="Celery workers" ok={data.celery?.ok}>
          {data.celery?.ok
            ? `${data.celery.workers?.length || 0} worker(s)`
            : data.celery?.detail || 'unreachable'}
        </Tile>
        <Tile title="Sentry" ok={data.sentry?.configured}>
          {data.sentry?.configured ? 'configured' : 'not configured'}
        </Tile>
      </div>

      <div className="rounded-card border border-line bg-surface p-4">
        <h2 className="mb-2 font-head font-semibold text-tx">Queue depth</h2>
        {queueErr ? (
          <p className="text-xs text-tx-3">Broker unavailable — {queueErr}</p>
        ) : (
          <div className="flex flex-wrap gap-4">
            {Object.entries(queues).map(([q, depth]) => (
              <div key={q} className="flex items-baseline gap-2">
                <span className="font-num text-2xl text-tx">{depth}</span>
                <span className="text-xs text-tx-3">{q}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
