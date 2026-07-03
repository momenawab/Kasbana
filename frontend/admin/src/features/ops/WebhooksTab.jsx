import { Loader2, RefreshCw } from 'lucide-react'
import { useWebhooks, useReplayWebhook } from './api'
import { normalizeError } from '../../lib/api'

function tone(status) {
  if (status === 'processed') return 'text-success'
  if (status === 'no_merchant' || status === 'failed' || status === 'invalid') return 'text-danger'
  return 'text-tx-3'
}

export default function WebhooksTab({ canManage }) {
  const { data: rows, isLoading } = useWebhooks({})
  const replay = useReplayWebhook()

  async function doReplay(id) {
    try {
      await replay.mutateAsync(id)
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  if (isLoading || !rows) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="border-b border-line text-tx-3">
          <tr className="text-left">
            <th className="px-4 py-3 font-medium">Provider</th>
            <th className="px-4 py-3 font-medium">Kind</th>
            <th className="px-4 py-3 font-medium">Gateway ref</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">When</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-tx-3">
                No webhook deliveries recorded.
              </td>
            </tr>
          )}
          {rows.map((w) => (
            <tr key={w.id} className="border-b border-line/60 last:border-0">
              <td className="px-4 py-2.5 text-tx-2">{w.provider}</td>
              <td className="px-4 py-2.5 text-tx-3">{w.kind || '—'}</td>
              <td className="px-4 py-2.5 font-num text-tx-3">{w.gateway_ref || '—'}</td>
              <td className={'px-4 py-2.5 font-semibold ' + tone(w.status)}>{w.status}</td>
              <td className="whitespace-nowrap px-4 py-2.5 text-tx-3">
                {new Date(w.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-2.5 text-right">
                {canManage && w.payload && Object.keys(w.payload).length > 0 && (
                  <button
                    onClick={() => doReplay(w.id)}
                    disabled={replay.isPending}
                    className="inline-flex items-center gap-1 rounded-ctl border border-line px-2.5 py-1 text-xs text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                  >
                    <RefreshCw size={13} /> Replay
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
