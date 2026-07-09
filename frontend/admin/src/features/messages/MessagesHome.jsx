import { useState } from 'react'
import {
  Loader2,
  Mail,
  Trash2,
  Check,
  RotateCcw,
  Reply,
  Send,
  X,
  Plus,
} from 'lucide-react'
import {
  useMessages,
  useUpdateMessage,
  useDeleteMessage,
  useReplyMessage,
  useCreateMessage,
} from './api'
import Badge from '../../components/Badge'
import { fromNow } from '../../lib/format'

const STATUS_TONE = { new: 'info', read: 'neutral', replied: 'success' }
const STATUS_LABEL = { new: 'New', read: 'Read', replied: 'Replied' }

export default function MessagesHome() {
  const { data, isLoading } = useMessages()
  const rows = data ?? []
  const newCount = rows.filter((r) => r.status === 'new').length
  const [showCreate, setShowCreate] = useState(false)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <h1 className="font-head text-2xl font-bold text-tx">Messages</h1>
        {newCount > 0 && <Badge tone="info">{newCount} new</Badge>}
        <button
          id="create-message-btn"
          onClick={() => setShowCreate((v) => !v)}
          className="ml-auto flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-d"
        >
          <Plus size={16} />
          Create Message
        </button>
      </div>
      <p className="-mt-3 text-sm text-tx-3">
        Support &amp; contact messages from the marketing site.
      </p>

      {showCreate && <CreateMessageForm onClose={() => setShowCreate(false)} />}

      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <List rows={rows} />
      )}
    </div>
  )
}

function CreateMessageForm({ onClose }) {
  const create = useCreateMessage()
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '' })

  const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))

  const canSubmit =
    form.name.trim() && form.email.trim() && form.subject.trim() && form.message.trim()

  async function handleSubmit(e) {
    e.preventDefault()
    if (!canSubmit) return
    try {
      await create.mutateAsync(form)
      onClose()
    } catch {
      // error is surfaced inline below
    }
  }

  const createError = create.isError
    ? create.error?.response?.data?.error?.message ||
      create.error?.response?.data?.email?.[0] ||
      'Could not create message. Please try again.'
    : null

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-card border border-brand/30 bg-surface p-5"
    >
      <h2 className="mb-4 text-sm font-semibold text-tx">
        New Message — set the recipient you want to email
      </h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="create-msg-name" className="mb-1 block text-xs font-medium text-tx-3">
            Name
          </label>
          <input
            id="create-msg-name"
            type="text"
            value={form.name}
            onChange={set('name')}
            placeholder="Customer name"
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </div>
        <div>
          <label htmlFor="create-msg-email" className="mb-1 block text-xs font-medium text-tx-3">
            Email
          </label>
          <input
            id="create-msg-email"
            type="email"
            value={form.email}
            onChange={set('email')}
            placeholder="recipient@example.com"
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
        </div>
      </div>
      <div className="mt-3">
        <label htmlFor="create-msg-subject" className="mb-1 block text-xs font-medium text-tx-3">
          Subject
        </label>
        <input
          id="create-msg-subject"
          type="text"
          value={form.subject}
          onChange={set('subject')}
          placeholder="Subject line"
          className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
        />
      </div>
      <div className="mt-3">
        <label htmlFor="create-msg-body" className="mb-1 block text-xs font-medium text-tx-3">
          Message body
        </label>
        <textarea
          id="create-msg-body"
          rows={4}
          value={form.message}
          onChange={set('message')}
          placeholder="Write the message content…"
          className="w-full rounded-ctl border border-line bg-surface-2 p-3 text-sm text-tx outline-none focus:border-brand"
        />
      </div>
      {createError && <p className="mt-2 text-xs text-danger">{createError}</p>}
      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:text-tx"
        >
          <X size={14} /> Cancel
        </button>
        <button
          type="submit"
          disabled={!canSubmit || create.isPending}
          className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
        >
          {create.isPending ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          Create
        </button>
      </div>
    </form>
  )
}

function List({ rows }) {
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
        <MessageRow key={m.id} m={m} />
      ))}
    </div>
  )
}

function MessageRow({ m }) {
  const update = useUpdateMessage()
  const del = useDeleteMessage()
  const reply = useReplyMessage()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')

  const replyError = reply.isError
    ? reply.error?.response?.data?.error?.message || 'Could not send the email. Please try again.'
    : null

  async function sendReply() {
    if (!text.trim()) return
    try {
      await reply.mutateAsync({ id: m.id, message: text })
      setText('')
      setOpen(false)
    } catch {
      // error is surfaced inline via replyError
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Badge tone={STATUS_TONE[m.status]}>{STATUS_LABEL[m.status] ?? m.status}</Badge>
            <span className="truncate font-semibold text-tx">{m.subject}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-tx-3">
            <span className="text-tx-2">{m.name}</span>
            <a href={`mailto:${m.email}`} className="flex items-center gap-1 hover:text-brand">
              <Mail size={12} /> {m.email}
            </a>
            <span>· {fromNow(m.created_at)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand"
          >
            <Reply size={14} /> Reply
          </button>
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

      {open && (
        <div className="mt-3 border-t border-line pt-3">
          <label className="mb-1 block text-xs font-semibold text-tx-3">
            Reply to {m.name} — they'll receive the branded Stampn email.
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={5}
            placeholder="Write your reply…"
            className="w-full rounded-ctl border border-line bg-surface-2 p-3 text-sm text-tx outline-none focus:border-brand"
          />
          {replyError && <p className="mt-1 text-xs text-danger">{replyError}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <button
              onClick={() => {
                setOpen(false)
                setText('')
                reply.reset()
              }}
              className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:text-tx"
            >
              <X size={14} /> Cancel
            </button>
            <button
              onClick={sendReply}
              disabled={reply.isPending || !text.trim()}
              className="flex items-center gap-1 rounded-ctl bg-brand px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
            >
              {reply.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
              Send reply
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
