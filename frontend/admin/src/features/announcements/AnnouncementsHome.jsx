import { useState } from 'react'
import { Loader2, Megaphone, Send, Trash2, Users } from 'lucide-react'
import {
  useAnnouncements,
  useAudiencePreview,
  useCreateAnnouncement,
  useSendAnnouncement,
  useDeleteAnnouncement,
} from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, fromNow } from '../../lib/format'

const MARKETING_ROLES = ['SUPER_ADMIN', 'MARKETING_ADMIN']

const AUDIENCES = [
  { key: 'all', label: 'All merchants' },
  { key: 'plan', label: 'By plan' },
  { key: 'trial_ending', label: 'Trial ending' },
  { key: 'at_risk', label: 'At-risk' },
  { key: 'active', label: 'Recently active' },
]
const PLANS = ['STARTER', 'GROWTH', 'CHAIN']
const CHANNELS = [
  { key: 'in_app', label: 'In-app' },
  { key: 'email', label: 'Email' },
  { key: 'both', label: 'In-app + email' },
]

const STATUS_TONE = { draft: 'neutral', scheduled: 'info', sent: 'success' }

export default function AnnouncementsHome() {
  const { role } = useAuth()
  const canBroadcast = MARKETING_ROLES.includes(role)
  const { data, isLoading } = useAnnouncements()
  const rows = data ?? []

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Announcements</h1>
      {canBroadcast && <Composer />}
      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <List rows={rows} canBroadcast={canBroadcast} />
      )}
    </div>
  )
}

function Composer() {
  const [form, setForm] = useState({
    title: '',
    body: '',
    channel: 'in_app',
    audience: 'all',
    audience_param: '',
  })
  const [msg, setMsg] = useState(null)
  const create = useCreateAnnouncement()
  const send = useSendAnnouncement()
  const preview = useAudiencePreview(form.audience, form.audience === 'plan' ? form.audience_param : '')

  function set(k, v) {
    setForm({ ...form, [k]: v })
  }

  async function createAndSend(sendNow) {
    setMsg(null)
    if (!form.title.trim() || !form.body.trim()) {
      setMsg('Title and body are required.')
      return
    }
    if (
      sendNow &&
      !window.confirm(
        `Broadcast "${form.title}" to ${preview.data?.recipients ?? '…'} merchant(s) via ${form.channel}?`
      )
    ) {
      return
    }
    try {
      const created = await create.mutateAsync(form)
      if (sendNow) await send.mutateAsync(created.id)
      setForm({ title: '', body: '', channel: 'in_app', audience: 'all', audience_param: '' })
      setMsg(sendNow ? 'Broadcast sent.' : 'Draft saved.')
    } catch (err) {
      setMsg(normalizeError(err).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center gap-2 text-tx">
        <Megaphone size={16} className="text-tx-3" />
        <h2 className="font-head text-sm font-semibold">New broadcast</h2>
      </div>
      <div className="flex flex-col gap-3">
        <input
          value={form.title}
          onChange={(e) => set('title', e.target.value)}
          placeholder="Title"
          className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
        />
        <textarea
          value={form.body}
          onChange={(e) => set('body', e.target.value)}
          rows={3}
          placeholder="Message…"
          className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-tx-3">
            Channel
            <select
              value={form.channel}
              onChange={(e) => set('channel', e.target.value)}
              className="mt-1 block rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx"
            >
              {CHANNELS.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-tx-3">
            Audience
            <select
              value={form.audience}
              onChange={(e) => set('audience', e.target.value)}
              className="mt-1 block rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx"
            >
              {AUDIENCES.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          {form.audience === 'plan' && (
            <label className="text-xs text-tx-3">
              Plan
              <select
                value={form.audience_param}
                onChange={(e) => set('audience_param', e.target.value)}
                className="mt-1 block rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx"
              >
                <option value="">—</option>
                {PLANS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
          )}
          <span className="flex items-center gap-1 text-sm text-tx-2">
            <Users size={14} className="text-tx-3" />
            {preview.isLoading ? '…' : num(preview.data?.recipients ?? 0)} recipients
          </span>
          <div className="ml-auto flex gap-2">
            <button
              onClick={() => createAndSend(false)}
              disabled={create.isPending}
              className="rounded-ctl border border-line bg-surface-2 px-4 py-2 text-sm font-semibold text-tx hover:border-brand disabled:opacity-60"
            >
              Save draft
            </button>
            <button
              onClick={() => createAndSend(true)}
              disabled={create.isPending || send.isPending}
              className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
            >
              <Send size={14} /> Send now
            </button>
          </div>
        </div>
        {msg && <p className="text-sm text-tx-2">{msg}</p>}
      </div>
    </div>
  )
}

function List({ rows, canBroadcast }) {
  const send = useSendAnnouncement()
  const del = useDeleteAnnouncement()

  if (rows.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
        No announcements yet.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {rows.map((a) => (
        <div
          key={a.id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-surface p-4"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>
              <span className="truncate text-tx">{a.title}</span>
            </div>
            <div className="mt-1 text-xs text-tx-3">
              {a.channel} · {a.audience}
              {a.audience_param ? ` (${a.audience_param})` : ''} ·{' '}
              {a.status === 'sent'
                ? `${num(a.recipients)} recipients · ${num(a.stats.opened)} opened (${Math.round(
                    a.stats.open_rate * 100
                  )}%)`
                : `created ${fromNow(a.created_at)}`}
            </div>
          </div>
          {canBroadcast && a.status !== 'sent' && (
            <div className="flex gap-2">
              <button
                onClick={() => send.mutate(a.id)}
                className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand"
              >
                <Send size={14} /> Send
              </button>
              <button
                onClick={() => del.mutate(a.id)}
                className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-danger hover:text-danger"
              >
                <Trash2 size={14} />
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
