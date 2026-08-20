import { useState } from 'react'
import { Loader2, RotateCw } from 'lucide-react'
import { useTasks, useRetryTask } from './api'
import { normalizeError } from '../../lib/api'

const FILTERS = ['', 'FAILURE', 'SUCCESS', 'STARTED', 'PENDING']

function tone(status) {
  if (status === 'SUCCESS') return 'text-success'
  if (status === 'FAILURE') return 'text-danger'
  return 'text-tx-3'
}

export default function JobsTab({ canManage }) {
  const [status, setStatus] = useState('FAILURE')
  const { data: tasks, isLoading } = useTasks(status)
  const retry = useRetryTask()

  async function doRetry(id) {
    try {
      await retry.mutateAsync(id)
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2">
        {FILTERS.map((f) => (
          <button
            key={f || 'all'}
            onClick={() => setStatus(f)}
            className={
              'rounded-ctl px-3 py-1.5 text-xs font-semibold ' +
              (status === f ? 'bg-brand text-white' : 'bg-surface-2 text-tx-3 hover:text-tx')
            }
          >
            {f || 'All'}
          </button>
        ))}
      </div>

      {isLoading || !tasks ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-tx-3">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium">Task</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">When</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-tx-3">
                    No tasks.
                  </td>
                </tr>
              )}
              {tasks.map((t) => (
                <tr key={t.task_id} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-2.5 font-num text-tx">{t.task_name}</td>
                  <td className={'px-4 py-2.5 font-semibold ' + tone(t.status)}>{t.status}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-tx-3">
                    {t.date_done ? new Date(t.date_done).toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {canManage && (
                      <button
                        onClick={() => doRetry(t.task_id)}
                        disabled={retry.isPending}
                        className="inline-flex items-center gap-1 rounded-ctl border border-line px-2.5 py-1 text-xs text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                      >
                        <RotateCw size={13} /> Retry
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
