import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  useSubscription,
  useSubscriptionAudit,
  useUpdateSubscription,
  useExtendTrial,
  useSetComp,
  useLockSubscription,
  useUnlockSubscription,
} from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { shortDate, fromNow, statusTone } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']
const PLANS = ['FREE', 'STARTER', 'GROWTH', 'CHAIN']
const STATUSES = ['TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELED', 'LOCKED']

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-tx-3">{label}</span>
      {children}
    </label>
  )
}

const inputClass =
  'w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand'

export default function SubscriptionTab({ merchantId }) {
  const { role } = useAuth()
  const canEdit = FINANCE_ROLES.includes(role)
  const { data: sub, isLoading } = useSubscription(merchantId)
  const { data: auditLog = [] } = useSubscriptionAudit(merchantId)
  const update = useUpdateSubscription(merchantId)
  const extendTrial = useExtendTrial(merchantId)
  const setComp = useSetComp(merchantId)
  const lockSub = useLockSubscription(merchantId)
  const unlockSub = useUnlockSubscription(merchantId)

  const [form, setForm] = useState(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [shortfall, setShortfall] = useState(null)
  const [days, setDays] = useState(14)
  const [compReason, setCompReason] = useState('')
  const [lockReason, setLockReason] = useState('')

  if (isLoading || !sub) {
    return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />
  }

  const f = form ?? {
    plan: sub.plan,
    status: sub.status,
    override_plan: sub.override_plan || '',
    override_expires_at: sub.override_expires_at ? sub.override_expires_at.slice(0, 16) : '',
    notes: sub.notes || '',
  }

  function set(field, value) {
    setForm({ ...f, [field]: value })
  }

  function patchBody(extra) {
    return {
      ...f,
      override_expires_at: f.override_expires_at ? new Date(f.override_expires_at).toISOString() : null,
      reason,
      ...extra,
    }
  }

  async function submitPatch(e) {
    e.preventDefault()
    setError('')
    setShortfall(null)
    try {
      await update.mutateAsync(patchBody())
      setForm(null)
      setReason('')
    } catch (err) {
      const { code, message } = normalizeError(err)
      if (code === 'PLAN_DOWNGRADE_BLOCKED') {
        setShortfall(err.response?.data?.error?.shortfall)
        setError('Downgrade blocked — usage exceeds the new plan’s limits.')
      } else {
        setError(message)
      }
    }
  }

  async function forcePatch() {
    setError('')
    try {
      await update.mutateAsync(patchBody({ force: true }))
      setShortfall(null)
      setForm(null)
      setReason('')
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  async function runExtendTrial() {
    setError('')
    try {
      await extendTrial.mutateAsync({ days: Number(days) })
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  async function runComp(on) {
    setError('')
    try {
      await setComp.mutateAsync({ on, reason: compReason })
      setCompReason('')
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  async function runLockToggle() {
    setError('')
    try {
      if (sub.status === 'LOCKED') {
        await unlockSub.mutateAsync({ reason: lockReason })
      } else {
        await lockSub.mutateAsync({ reason: lockReason })
      }
      setLockReason('')
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  const busy =
    update.isPending ||
    extendTrial.isPending ||
    setComp.isPending ||
    lockSub.isPending ||
    unlockSub.isPending

  return (
    <div className="flex flex-col gap-4">
      {/* Current state */}
      <div className="flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface p-4">
        <Badge tone="brand">{sub.plan}</Badge>
        <Badge tone={statusTone(sub.status)}>{sub.status}</Badge>
        {sub.comp && <Badge tone="success">Comp</Badge>}
        {sub.override_plan && <Badge tone="info">Override → {sub.override_plan}</Badge>}
        <span className="text-xs text-tx-3">
          Effective plan: <span className="font-semibold text-tx-2">{sub.effective_plan ?? 'locked'}</span>
        </span>
        {sub.trial_ends_at && (
          <span className="text-xs text-tx-3">Trial ends {shortDate(sub.trial_ends_at)}</span>
        )}
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {shortfall && (
        <div className="rounded-card border border-danger/40 bg-surface p-4 text-sm">
          <p className="mb-2 text-tx-2">Usage exceeds the target plan:</p>
          <ul className="mb-3 list-inside list-disc text-tx-3">
            {Object.entries(shortfall).map(([cap, { usage, limit }]) => (
              <li key={cap}>
                {cap}: {usage} used, limit is {limit}
              </li>
            ))}
          </ul>
          <button
            onClick={forcePatch}
            className="rounded-ctl bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90"
          >
            Downgrade anyway
          </button>
        </div>
      )}

      {canEdit && (
        <>
          {/* Plan / status / override / notes */}
          <form
            onSubmit={submitPatch}
            className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4"
          >
            <h3 className="font-head text-sm font-semibold text-tx">Plan &amp; status</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Plan">
                <select value={f.plan} onChange={(e) => set('plan', e.target.value)} className={inputClass}>
                  {PLANS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Status">
                <select
                  value={f.status}
                  onChange={(e) => set('status', e.target.value)}
                  className={inputClass}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Override plan (blank = none)">
                <select
                  value={f.override_plan}
                  onChange={(e) => set('override_plan', e.target.value)}
                  className={inputClass}
                >
                  <option value="">None</option>
                  {PLANS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Override expires (blank = indefinite)">
                <input
                  type="datetime-local"
                  value={f.override_expires_at}
                  onChange={(e) => set('override_expires_at', e.target.value)}
                  className={inputClass}
                />
              </Field>
            </div>
            <Field label="Notes">
              <textarea
                value={f.notes}
                onChange={(e) => set('notes', e.target.value)}
                rows={2}
                className={inputClass}
              />
            </Field>
            <Field label="Reason (required)">
              <input value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass} />
            </Field>
            <button
              type="submit"
              disabled={busy || !reason}
              className="w-fit rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
            >
              Save changes
            </button>
          </form>

          {/* Quick actions */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-card border border-line bg-surface p-4">
              <h3 className="mb-2 font-head text-sm font-semibold text-tx">Extend trial</h3>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                  className={inputClass}
                />
                <button
                  onClick={runExtendTrial}
                  disabled={busy}
                  className="shrink-0 rounded-ctl border border-line px-3 py-2 text-xs font-semibold text-tx hover:bg-surface-2 disabled:opacity-60"
                >
                  Extend
                </button>
              </div>
            </div>

            <div className="rounded-card border border-line bg-surface p-4">
              <h3 className="mb-2 font-head text-sm font-semibold text-tx">Comp (free access)</h3>
              <input
                placeholder="Reason"
                value={compReason}
                onChange={(e) => setCompReason(e.target.value)}
                className={`${inputClass} mb-2`}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => runComp(true)}
                  disabled={busy || !compReason}
                  className="flex-1 rounded-ctl border border-line px-3 py-2 text-xs font-semibold text-tx hover:bg-surface-2 disabled:opacity-60"
                >
                  Turn on
                </button>
                <button
                  onClick={() => runComp(false)}
                  disabled={busy || !compReason}
                  className="flex-1 rounded-ctl border border-line px-3 py-2 text-xs font-semibold text-tx hover:bg-surface-2 disabled:opacity-60"
                >
                  Turn off
                </button>
              </div>
            </div>

            <div className="rounded-card border border-line bg-surface p-4">
              <h3 className="mb-2 font-head text-sm font-semibold text-tx">
                {sub.status === 'LOCKED' ? 'Unlock' : 'Lock'}
              </h3>
              <input
                placeholder="Reason"
                value={lockReason}
                onChange={(e) => setLockReason(e.target.value)}
                className={`${inputClass} mb-2`}
              />
              <button
                onClick={runLockToggle}
                disabled={busy || !lockReason}
                className="w-full rounded-ctl border border-danger/40 px-3 py-2 text-xs font-semibold text-danger hover:bg-surface-2 disabled:opacity-60"
              >
                {sub.status === 'LOCKED' ? 'Unlock merchant' : 'Lock merchant'}
              </button>
            </div>
          </div>
        </>
      )}

      {/* Audit trail */}
      <div className="rounded-card border border-line bg-surface p-4">
        <h3 className="mb-3 font-head text-sm font-semibold text-tx">Recent changes</h3>
        {auditLog.length === 0 ? (
          <p className="text-sm text-tx-3">No changes yet.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {auditLog.map((row, i) => (
              <li key={i} className="border-b border-line/60 pb-2 last:border-0">
                <div className="flex justify-between text-tx-2">
                  <span className="font-semibold">{row.action.replace('subscription.', '')}</span>
                  <span className="text-xs text-tx-3">{fromNow(row.created_at)}</span>
                </div>
                <div className="text-xs text-tx-3">
                  {row.actor_email}
                  {row.metadata?.reason ? ` — ${row.metadata.reason}` : ''}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
