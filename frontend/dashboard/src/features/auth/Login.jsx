// Phase-1 Login stub — establishes a session so the Shell is reachable.
// Phase 3 replaces this with the full rhf+zod screen (spec §14 Login).
import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { login, normalizeError } from '../../lib/api'

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const qc = useQueryClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate(decodeURIComponent(params.get('next') || '/'), { replace: true })
    } catch (err) {
      setError(normalizeError(err).message || t('login.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-card bg-white p-6 shadow-bold">
        <h1 className="mb-4 font-head text-2xl font-bold text-ink">{t('login.title')}</h1>
        <label className="mb-1 block text-sm text-tx-2">{t('login.email')}</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-3 w-full rounded-ctl border border-line px-3 py-2"
          required
        />
        <label className="mb-1 block text-sm text-tx-2">{t('login.password')}</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-3 w-full rounded-ctl border border-line px-3 py-2"
          required
        />
        {error && <p className="mb-3 text-sm text-danger">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-ctl bg-amber py-2 font-semibold text-ink disabled:opacity-60"
        >
          {t('login.submit')}
        </button>
        <div className="mt-3 flex justify-between text-sm text-tx-2">
          <Link to="/forgot">{t('login.forgot')}</Link>
          <Link to="/signup">{t('login.signup')}</Link>
        </div>
      </form>
    </div>
  )
}
