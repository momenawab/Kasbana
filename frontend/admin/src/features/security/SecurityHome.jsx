import { useState } from 'react'
import { Loader2, LogOut, Monitor, ShieldCheck, ShieldPlus } from 'lucide-react'
import {
  useSessions,
  useRevokeSession,
  useLogoutEverywhere,
  useMfaSetup,
  useMfaConfirm,
} from './api'
import { useAuth } from '../../hooks/useAuth'
import { normalizeError } from '../../lib/api'

export default function SecurityHome() {
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <h1 className="font-head text-2xl font-bold text-tx">Security</h1>
      <MfaCard />
      <SessionsCard />
    </div>
  )
}

function MfaCard() {
  const { admin } = useAuth()
  const setup = useMfaSetup()
  const confirm = useMfaConfirm()
  const [enrol, setEnrol] = useState(null) // { qr, secret }
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')

  async function startEnrol() {
    setErr('')
    try {
      setEnrol(await setup.mutateAsync())
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  async function finishEnrol() {
    setErr('')
    try {
      await confirm.mutateAsync(code.trim())
      setEnrol(null)
      setCode('')
    } catch (e) {
      setErr(normalizeError(e).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck size={18} className={admin?.mfa_enabled ? 'text-success' : 'text-tx-3'} />
          <h2 className="font-head font-semibold text-tx">Two-factor authentication</h2>
        </div>
        <span
          className={
            'rounded-full px-3 py-1 text-xs font-semibold ' +
            (admin?.mfa_enabled ? 'bg-success/15 text-success' : 'bg-surface-2 text-tx-3')
          }
        >
          {admin?.mfa_enabled ? 'Enabled' : 'Off'}
        </span>
      </div>

      {admin?.mfa_enabled ? (
        <p className="mt-2 text-sm text-tx-3">
          Your account is protected with an authenticator app. Lost your device? Ask a super-admin
          to reset your MFA from the Admin Team screen.
        </p>
      ) : enrol ? (
        <div className="mt-3 flex flex-col items-center gap-3 text-center">
          <p className="text-sm text-tx-2">Scan with an authenticator app, then enter the code.</p>
          <img src={enrol.qr} alt="TOTP QR" className="h-40 w-40 rounded-ctl bg-white p-2" />
          <code className="break-all rounded-ctl bg-surface-2 px-2 py-1 text-xs text-tx-3">
            {enrol.secret}
          </code>
          <div className="flex w-full max-w-xs items-center gap-2">
            <input
              inputMode="numeric"
              dir="ltr"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              className="flex-1 rounded-ctl border border-line bg-bg px-3 py-2 text-center font-num tracking-widest text-tx outline-none focus:border-brand"
            />
            <button
              onClick={finishEnrol}
              disabled={confirm.isPending || code.trim().length < 6}
              className="rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Confirm
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <p className="mb-2 text-sm text-tx-3">
            Add an extra layer of protection with a time-based one-time code.
          </p>
          <button
            onClick={startEnrol}
            disabled={setup.isPending}
            className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm font-semibold text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
          >
            <ShieldPlus size={15} /> Enable 2FA
          </button>
        </div>
      )}
      {err && <p className="mt-2 text-sm text-danger">{err}</p>}
    </div>
  )
}

function SessionsCard() {
  const { data: sessions, isLoading } = useSessions()
  const revoke = useRevokeSession()
  const logoutAll = useLogoutEverywhere()

  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Monitor size={18} className="text-tx-2" />
          <h2 className="font-head font-semibold text-tx">Active sessions</h2>
        </div>
        <button
          onClick={() => logoutAll.mutate()}
          disabled={logoutAll.isPending}
          className="flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-danger hover:text-danger disabled:opacity-60"
        >
          <LogOut size={14} /> Log out other devices
        </button>
      </div>

      {isLoading || !sessions ? (
        <Loader2 className="animate-spin text-tx-3" />
      ) : (
        <div className="flex flex-col gap-2">
          {sessions.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between rounded-ctl border border-line/60 px-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <div className="truncate text-tx-2" title={s.user_agent}>
                  {s.user_agent || 'Unknown device'}
                  {s.current && <span className="ml-2 text-xs text-brand">this device</span>}
                </div>
                <div className="text-xs text-tx-3">
                  {s.ip || '—'} · last seen{' '}
                  {s.last_seen_at ? new Date(s.last_seen_at).toLocaleString() : '—'}
                </div>
              </div>
              {!s.current && (
                <button
                  onClick={() => revoke.mutate(s.id)}
                  className="rounded-ctl px-2 py-1 text-xs text-tx-3 hover:text-danger"
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
