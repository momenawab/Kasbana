import { useState } from 'react'
import { Loader2, RotateCw } from 'lucide-react'
import { useWalletFailures, useReprovision } from './api'
import { normalizeError } from '../../lib/api'

export default function WalletTab({ canManage }) {
  const [resolved, setResolved] = useState('false')
  const { data: rows, isLoading } = useWalletFailures(resolved)
  const reprovision = useReprovision()

  async function doReprovision(id) {
    try {
      await reprovision.mutateAsync(id)
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        {[
          ['false', 'Unresolved'],
          ['true', 'Resolved'],
        ].map(([val, label]) => (
          <button
            key={val}
            onClick={() => setResolved(val)}
            className={
              'rounded-ctl px-3 py-1.5 text-xs font-semibold ' +
              (resolved === val ? 'bg-brand text-white' : 'bg-surface-2 text-tx-3 hover:text-tx')
            }
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading || !rows ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Operation</th>
                <th className="px-4 py-3 font-medium">Platform</th>
                <th className="px-4 py-3 font-medium">Card</th>
                <th className="px-4 py-3 font-medium">Error</th>
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-tx-3">
                    No failures here.
                  </td>
                </tr>
              )}
              {rows.map((f) => (
                <tr key={f.id} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-2.5 text-tx-2">{f.operation}</td>
                  <td className="px-4 py-2.5 text-tx-3">{f.platform || '—'}</td>
                  <td className="px-4 py-2.5 font-num text-tx-3">
                    {f.customer_card_id ? f.customer_card_id.slice(0, 8) : '— gone'}
                  </td>
                  <td className="max-w-xs truncate px-4 py-2.5 text-tx-3" title={f.error}>
                    {f.error || '—'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-tx-3">
                    {new Date(f.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {canManage && !f.resolved && f.customer_card_id && (
                      <button
                        onClick={() => doReprovision(f.id)}
                        disabled={reprovision.isPending}
                        className="inline-flex items-center gap-1 rounded-ctl border border-line px-2.5 py-1 text-xs text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                      >
                        <RotateCw size={13} /> Re-provision
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
