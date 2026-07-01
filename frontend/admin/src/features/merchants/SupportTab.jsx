import { useState } from 'react'
import { Loader2, Eye, KeyRound, Mail, Unplug, MessageSquare } from 'lucide-react'
import {
  useSupportNotes,
  useAddSupportNote,
  useImpersonations,
  useStartImpersonation,
  useSendPasswordReset,
  useResendInvite,
  useClearStuckCheckout,
} from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { fromNow, shortDate } from '../../lib/format'

const SUPPORT_ROLES = ['SUPER_ADMIN', 'SUPPORT']
// Where the merchant dashboard lives — the impersonation token is handed off via
// its URL fragment. Prod bakes app.stampn.net; dev points at the local dashboard.
const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL || 'https://app.stampn.net'

function ActionCard({ icon: Icon, title, children }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex items-center gap-2 text-tx">
        <Icon size={16} className="text-tx-3" />
        <h3 className="font-head text-sm font-semibold">{title}</h3>
      </div>
      {children}
    </div>
  )
}

export default function SupportTab({ merchantId, merchantName }) {
  const { role } = useAuth()
  const canAct = SUPPORT_ROLES.includes(role)

  const notes = useSupportNotes(merchantId)
  const addNote = useAddSupportNote(merchantId)
  const impersonations = useImpersonations(merchantId)
  const startImpersonation = useStartImpersonation(merchantId)
  const sendReset = useSendPasswordReset(merchantId)
  const resendInvite = useResendInvite(merchantId)
  const clearCheckout = useClearStuckCheckout(merchantId)

  const [noteBody, setNoteBody] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [banner, setBanner] = useState(null) // { tone, text }

  function flash(tone, text) {
    setBanner({ tone, text })
    setTimeout(() => setBanner(null), 6000)
  }

  async function viewAsMerchant() {
    const reason = window.prompt('Reason for impersonating this merchant (audited):')
    if (!reason) return
    try {
      const res = await startImpersonation.mutateAsync({ reason })
      const url = `${DASHBOARD_URL}/#impersonate=${encodeURIComponent(res.access)}`
      window.open(url, '_blank', 'noopener')
      flash('info', `Opened a view-as session as ${res.target_email} (expires ${shortDate(res.expires_at)}).`)
    } catch (err) {
      flash('danger', normalizeError(err).message)
    }
  }

  async function runAction(mutation, body, ok) {
    try {
      await mutation.mutateAsync(body)
      flash('success', ok)
    } catch (err) {
      flash('danger', normalizeError(err).message)
    }
  }

  async function submitNote(e) {
    e.preventDefault()
    if (!noteBody.trim()) return
    try {
      await addNote.mutateAsync({ body: noteBody.trim() })
      setNoteBody('')
    } catch (err) {
      flash('danger', normalizeError(err).message)
    }
  }

  if (!canAct) {
    return (
      <div className="rounded-card border border-line bg-surface p-6 text-sm text-tx-3">
        Support tools (impersonation, account actions, notes) are available to Support and
        Super-admin roles. You can view the notes thread and activity timeline.
        <NotesThread notes={notes} readOnly />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {banner && (
        <div className="rounded-card border border-line bg-surface p-3 text-sm">
          <Badge tone={banner.tone === 'danger' ? 'danger' : banner.tone === 'success' ? 'success' : 'info'}>
            {banner.tone === 'danger' ? 'Error' : 'Done'}
          </Badge>
          <span className="ml-2 text-tx-2">{banner.text}</span>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <ActionCard icon={Eye} title="View as merchant">
          <p className="mb-3 text-xs text-tx-3">
            Opens the merchant dashboard in a time-limited, fully audited session with a
            persistent banner. Never for billing actions.
          </p>
          <button
            onClick={viewAsMerchant}
            disabled={startImpersonation.isPending}
            className="rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg hover:bg-brand-d disabled:opacity-60"
          >
            {startImpersonation.isPending ? 'Opening…' : `View as ${merchantName || 'merchant'}`}
          </button>
        </ActionCard>

        <ActionCard icon={KeyRound} title="Send password reset">
          <p className="mb-3 text-xs text-tx-3">
            Emails the merchant owner a 1-hour reset link.
          </p>
          <button
            onClick={() => runAction(sendReset, undefined, 'Password reset email sent to the owner.')}
            disabled={sendReset.isPending}
            className="rounded-ctl border border-line bg-surface-2 px-4 py-2 text-sm font-semibold text-tx hover:border-brand disabled:opacity-60"
          >
            Send reset link
          </button>
        </ActionCard>

        <ActionCard icon={Mail} title="Resend staff invite">
          <div className="flex gap-2">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="staff@shop.com"
              className="flex-1 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
            />
            <button
              onClick={() =>
                runAction(resendInvite, { email: inviteEmail }, 'Invite re-sent and its expiry refreshed.').then(
                  () => setInviteEmail('')
                )
              }
              disabled={resendInvite.isPending || !inviteEmail}
              className="rounded-ctl border border-line bg-surface-2 px-4 py-2 text-sm font-semibold text-tx hover:border-brand disabled:opacity-60"
            >
              Resend
            </button>
          </div>
        </ActionCard>

        <ActionCard icon={Unplug} title="Clear stuck checkout">
          <p className="mb-3 text-xs text-tx-3">
            Drops an abandoned pending checkout so subscribe/retry stop resolving through it.
          </p>
          <button
            onClick={() => {
              const reason = window.prompt('Reason (audited):')
              if (reason) runAction(clearCheckout, { reason }, 'Pending checkout cleared.')
            }}
            disabled={clearCheckout.isPending}
            className="rounded-ctl border border-line bg-surface-2 px-4 py-2 text-sm font-semibold text-tx hover:border-brand disabled:opacity-60"
          >
            Clear pending checkout
          </button>
        </ActionCard>
      </div>

      {/* Recent impersonation sessions */}
      <div className="rounded-card border border-line bg-surface p-4">
        <h3 className="mb-3 font-head text-sm font-semibold text-tx">Recent view-as sessions</h3>
        {impersonations.isLoading ? (
          <Loader2 size={16} className="animate-spin text-tx-3" />
        ) : (impersonations.data ?? []).length === 0 ? (
          <p className="text-sm text-tx-3">No impersonation sessions yet.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {impersonations.data.map((s) => (
              <li key={s.id} className="flex items-center justify-between border-b border-line/60 pb-2 last:border-0">
                <span className="text-tx-2">
                  {s.admin_email} → {s.target_email}
                  <span className="ml-2 text-xs text-tx-3">{s.reason}</span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge tone={s.active ? 'info' : 'neutral'}>{s.active ? 'active' : 'ended'}</Badge>
                  <span className="text-xs text-tx-3">{fromNow(s.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Notes thread */}
      <div className="rounded-card border border-line bg-surface p-4">
        <div className="mb-3 flex items-center gap-2 text-tx">
          <MessageSquare size={16} className="text-tx-3" />
          <h3 className="font-head text-sm font-semibold">Support notes</h3>
        </div>
        <form onSubmit={submitNote} className="mb-4 flex flex-col gap-2">
          <textarea
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            rows={2}
            placeholder="Add a note about this merchant…"
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
          />
          <button
            type="submit"
            disabled={addNote.isPending || !noteBody.trim()}
            className="w-fit rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg hover:bg-brand-d disabled:opacity-60"
          >
            Add note
          </button>
        </form>
        <NotesThread notes={notes} />
      </div>
    </div>
  )
}

function NotesThread({ notes, readOnly }) {
  if (notes.isLoading) return <Loader2 size={16} className="animate-spin text-tx-3" />
  const rows = notes.data ?? []
  if (rows.length === 0) {
    return <p className={readOnly ? 'mt-3 text-sm text-tx-3' : 'text-sm text-tx-3'}>No notes yet.</p>
  }
  return (
    <ul className={'flex flex-col gap-3' + (readOnly ? ' mt-3' : '')}>
      {rows.map((n) => (
        <li key={n.id} className="border-b border-line/60 pb-3 last:border-0">
          <div className="flex items-center justify-between text-xs text-tx-3">
            <span>{n.admin_email}</span>
            <span>{fromNow(n.created_at)}</span>
          </div>
          <p className="mt-1 whitespace-pre-wrap text-sm text-tx-2">{n.body}</p>
        </li>
      ))}
    </ul>
  )
}
