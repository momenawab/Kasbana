import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, Loader2 } from 'lucide-react'
import api, { normalizeError } from '../../lib/api'
import { setTokens } from '../../lib/auth'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const { data } = await api.post('/auth/login', { email, password })
      setTokens(data)
      navigate('/', { replace: true })
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
            <ShieldCheck size={22} />
          </div>
          <h1 className="font-head text-xl font-bold text-tx">Stampn Admin</h1>
          <p className="text-sm text-tx-3">Platform operations console</p>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
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
      </div>
    </div>
  )
}
