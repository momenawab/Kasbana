import { Loader2, Mail, Trash2, Check, RotateCcw } from 'lucide-react'
import { useMessages, useUpdateMessage, useDeleteMessage } from './api'
import Badge from '../../components/Badge'
import { fromNow } from '../../lib/format'

const STATUS_TONE = { new: 'info', read: 'neutral' }
const STATUS_LABEL = { new: 'New', read: 'Read' }

export default function MessagesHome() {
  const { data, isLoading } = useMessages()
  const rows = data ?? []
  const newCount = rows.filter((r) => r.status === 'new').length

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <h1 className="font-head text-2xl font-bold text-tx">Messages</h1>
        {newCount > 0 && <Badge tone="info">{newCount} new</Badge>}
      </div>
      <p className="-mt-3 text-sm text-tx-3">
        Support &amp; contact messages from the marketing site.
      </p>

      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <List rows={rows} />
      )}
    </div>
  )
}

function List({ rows }) {
  const update = useUpdateMessage()
  const del = useDeleteMessage()

  if (rows.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
        No messages yet.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.map((m) => (
        <div
          key={m.id}
          className="rounded-card border border-line bg-surface p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Badge tone={STATUS_TONE[m.status]}>
                  {STATUS_LABEL[m.status] ?? m.status}
                </Badge>
                <span className="truncate font-semibold text-tx">{m.subject}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-tx-3">
                <span className="text-tx-2">{m.name}</span>
                <a
                  href={`mailto:${m.email}`}
                  className="flex items-center gap-1 hover:text-brand"
                >
                  <Mail size={12} /> {m.email}
                </a>
                <span>· {fromNow(m.created_at)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              {m.status === 'new' ? (
                <button
                  onClick={() => update.mutate({ id: m.id, status: 'read' })}
                  disabled={update.isPending}
                  className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                >
                  <Check size={14} /> Mark read
                </button>
              ) : (
                <button
                  onClick={() => update.mutate({ id: m.id, status: 'new' })}
                  disabled={update.isPending}
                  className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                >
                  <RotateCcw size={14} /> Unread
                </button>
              )}
              <button
                onClick={() => {
                  if (window.confirm(`Delete message from ${m.name}?`)) {
                    del.mutate(m.id)
                  }
                }}
                disabled={del.isPending}
                className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-danger hover:text-danger disabled:opacity-60"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
          <p className="mt-3 whitespace-pre-wrap border-t border-line pt-3 text-sm text-tx-2">
            {m.message}
          </p>
        </div>
      ))}
    </div>
  )
}
