import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Loader2, KeyRound } from 'lucide-react'
import api, { normalizeError } from '../../lib/api'
import { setTokens } from '../../lib/auth'

// Login is a two-step flow (Phase 15): password first, then a TOTP gate. The
// server tells us which gate via `status`: `ok` (done), `mfa_required` (enter a
// code) or `mfa_setup` (enrol first — it returns a QR + secret).
export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // MFA step state
  const [stage, setStage] = useState('password') // 'password' | 'mfa'
  const [pending, setPending] = useState(null) // { pending_token, status, otpauth_uri, secret, qr }
  const [code, setCode] = useState('')

  function finish(data) {
    setTokens(data)
    navigate('/', { replace: true })
  }

  async function submitPassword(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { data } = await api.post('/auth/login', { email, password })
      if (data.status === 'ok') {
        finish(data)
      } else {
        setPending(data)
        setStage('mfa')
      }
    } catch (err) {
      setError(normalizeError(err).message)
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { data } = await api.post('/auth/mfa/verify', {
        pending_token: pending.pending_token,
        code: code.trim(),
      })
      finish(data)
    } catch (err) {
      setError(normalizeError(err).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-card border border-line bg-surface p-7 shadow-card">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-ctl bg-brand-bg text-brand">
            {stage === 'mfa' ? <KeyRound size={22} /> : <ShieldCheck size={22} />}
          </div>
          <h1 className="font-head text-xl font-bold text-tx">Stampn Admin</h1>
          <p className="text-sm text-tx-3">Platform operations console</p>
        </div>

        {stage === 'password' && (
          <form onSubmit={submitPassword} className="flex flex-col gap-3" noValidate>
            <label className="block">
              <span className="mb-1 block text-sm text-tx-2">Email</span>
              <input
                type="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
                autoComplete="username"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-tx-2">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
                autoComplete="current-password"
              />
            </label>

            {error && <p className="text-sm text-danger">{error}</p>}

            <button
              type="submit"
              disabled={busy || !email || !password}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-ctl bg-brand px-4 py-2 font-semibold text-bg transition hover:bg-brand-d disabled:opacity-60"
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              Sign in
            </button>
          </form>
        )}

        {stage === 'mfa' && (
          <form onSubmit={submitCode} className="flex flex-col gap-3" noValidate>
            {pending?.status === 'mfa_setup' ? (
              <div className="flex flex-col items-center gap-2 text-center">
                <p className="text-sm text-tx-2">
                  Two-factor is required for your role. Scan this with an authenticator app (Google
                  Authenticator, 1Password, Authy), then enter the 6-digit code.
                </p>
                {pending.qr && (
                  <img
                    src={pending.qr}
                    alt="TOTP QR code"
                    className="h-40 w-40 rounded-ctl bg-white p-2"
                  />
                )}
                <code className="break-all rounded-ctl bg-surface-2 px-2 py-1 text-xs text-tx-3">
                  {pending.secret}
                </code>
              </div>
            ) : (
              <p className="text-center text-sm text-tx-2">
                Enter the 6-digit code from your authenticator app.
              </p>
            )}

            <label className="block">
              <span className="mb-1 block text-sm text-tx-2">Authentication code</span>
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                dir="ltr"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="123456"
                className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-center font-num tracking-widest text-tx outline-none focus:border-brand"
                autoFocus
              />
            </label>

            {error && <p className="text-sm text-danger">{error}</p>}

            <button
              type="submit"
              disabled={busy || code.trim().length < 6}
              className="mt-1 inline-flex items-center justify-center gap-2 rounded-ctl bg-brand px-4 py-2 font-semibold text-bg transition hover:bg-brand-d disabled:opacity-60"
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              {pending?.status === 'mfa_setup' ? 'Verify & enrol' : 'Verify'}
            </button>
            <button
              type="button"
              onClick={() => {
                setStage('password')
                setCode('')
                setError('')
              }}
              className="text-xs text-tx-3 hover:text-tx-2"
            >
              Back
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
