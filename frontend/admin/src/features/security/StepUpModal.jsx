import { useState } from 'react'
import { Loader2, ShieldAlert, X } from 'lucide-react'
import { stepUp } from './api'
import { useAuth } from '../../hooks/useAuth'
import { normalizeError } from '../../lib/api'

// Reusable step-up prompt: re-prove password (+ TOTP if the admin has MFA) to
// refresh the session's recent-auth window, then run `onConfirmed` (e.g. retry
// the sensitive action). Shown when an endpoint returns 403 STEP_UP_REQUIRED.
export default function StepUpModal({ onClose, onConfirmed }) {
  const { admin } = useAuth()
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await stepUp({ password, code: code.trim() })
      await onConfirmed()
      onClose()
    } catch (e2) {
      setErr(normalizeError(e2).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="w-full max-w-sm rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-3 flex items-start justify-between">
          <div className="flex items-center gap-2 text-tx">
            <ShieldAlert size={18} className="text-warn" />
            <h2 className="font-head font-semibold">Confirm it&apos;s you</h2>
          </div>
          <button type="button" onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>
        <p className="mb-3 text-sm text-tx-3">
          This is a sensitive action. Re-enter your password
          {admin?.mfa_enabled ? ' and a code' : ''} to continue.
        </p>
        <label className="mb-2 block">
          <span className="mb-1 block text-sm text-tx-2">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="w-full rounded-ctl border border-line bg-bg px-3 py-2 text-tx outline-none focus:border-brand"
          />
        </label>
        {admin?.mfa_enabled && (
          <label className="mb-2 block">
            <span className="mb-1 block text-sm text-tx-2">Authentication code</span>
            <input
              inputMode="numeric"
              dir="ltr"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              className="w-full rounded-ctl border border-line bg-bg px-3 py-2 text-center font-num tracking-widest text-tx outline-none focus:border-brand"
            />
          </label>
        )}
        {err && <p className="mb-2 text-sm text-danger">{err}</p>}
        <button
          type="submit"
          disabled={busy || !password}
          className="mt-1 flex w-full items-center justify-center gap-2 rounded-ctl bg-brand px-4 py-2 font-semibold text-bg disabled:opacity-60"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          Confirm
        </button>
      </form>
    </div>
  )
}
