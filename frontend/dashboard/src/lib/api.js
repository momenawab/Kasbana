// Single axios instance + auth helpers (spec §5).
// - request interceptor attaches Bearer access
// - response interceptor: on 401 refresh once + retry, else log out
// - error envelope {error:{code,message,fields}} surfaced via normalizeError()
import axios from 'axios'
import { clearSession, getAccess, getRefresh, setAccess, setTokens } from './auth'
import { queryClient } from './queryClient'
import { gating } from './gating'

const BASE = (import.meta.env.VITE_API_URL || '') + '/api/v1'

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use((config) => {
  const access = getAccess()
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

let refreshing = null

async function refreshAccess() {
  const refresh = getRefresh()
  if (!refresh) throw new Error('no-refresh')
  // Raw axios (not the instance) so this call skips the interceptors.
  const { data } = await axios.post(`${BASE}/auth/refresh`, { refresh })
  setAccess(data.access)
  return data.access
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const { response, config } = error
    if (response?.status === 401 && !config.__retried && getRefresh()) {
      config.__retried = true
      try {
        refreshing = refreshing || refreshAccess()
        await refreshing
        refreshing = null
        return api(config)
      } catch {
        refreshing = null
        logout()
      }
    }
    // Server-side plan limit → open the UpgradeDrawer (spec §5/§12).
    if (response?.data?.error?.code === 'PLAN_LIMIT') {
      gating.open(response.data.error.message || null)
    }
    return Promise.reject(error)
  }
)

/**
 * Axios config carrying a fresh Idempotency-Key header. Use on mutating loyalty
 * calls (stamp/redeem) so a replayed request (proxy retry, lost response) is
 * de-duplicated server-side instead of double-stamping. The key rides on the
 * request, so an identical replay reuses it; a new user action gets a new key.
 */
export function idempotent() {
  const uuid =
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return { headers: { 'Idempotency-Key': uuid } }
}

function toFieldText(value) {
  if (Array.isArray(value)) return value.map(toFieldText).filter(Boolean).join('; ')
  return value == null ? '' : String(value)
}

function flattenFields(fields) {
  if (!fields || typeof fields !== 'object') return null
  const out = {}
  for (const [key, value] of Object.entries(fields)) {
    const text = toFieldText(value)
    if (text) out[key] = text
  }
  return Object.keys(out).length ? out : null
}

/**
 * Turn an axios error into the contract envelope shape for callers/forms.
 *
 * Returns:
 *  - code:   contract error code (or NETWORK_ERROR / SERVER_ERROR)
 *  - message: single human-readable line = backend message + field reasons
 *  - fields:  { field: 'reason string' } for inline form binding (DRF sends arrays)
 *  - status:  HTTP status (null when the request never reached the backend)
 *
 * In dev the raw envelope is logged so you can tell at a glance whether the
 * failure is backend (status + fields) or frontend (network/offline).
 */
export function normalizeError(error) {
  const status = error?.response?.status
  const body = error?.response?.data?.error

  // No HTTP response => the request never reached the backend (network/CORS/down).
  if (!error?.response) {
    const message =
      "Network error — couldn't reach the server. Check your connection or that the backend is running."
    if (import.meta.env.DEV) {
      console.error('[api error] no response (network/offline)', error?.message)
    }
    return { code: 'NETWORK_ERROR', message, fields: null, status: null }
  }

  const code = body?.code || 'SERVER_ERROR'
  const base = body?.message || 'Something went wrong.'
  const fields = flattenFields(body?.fields)
  const message = fields
    ? `${base} — ${Object.entries(fields)
        .map(([k, v]) => `${k}: ${v}`)
        .join('; ')}`
    : base

  if (import.meta.env.DEV) {
    console.error('[api error]', { status, code, message, fields })
  }

  return { code, message, fields, status }
}

export async function login(email, password) {
  const { data } = await api.post('/auth/token', { email, password })
  setTokens({ access: data.access, refresh: data.refresh })
  return data
}

// Register a merchant + owner and start the trial; returns a token pair.
export async function signup(payload) {
  const { data } = await api.post('/auth/signup', payload)
  setTokens({ access: data.access, refresh: data.refresh })
  return data
}

// Accept a staff invite (set password) and start a session.
export async function acceptInvite(token, password) {
  const { data } = await api.post(`/auth/invite/${token}`, { password })
  setTokens({ access: data.access, refresh: data.refresh })
  return data
}

export function logout() {
  clearSession()
  queryClient.clear()
  if (window.location.pathname !== '/login') window.location.assign('/login')
}

/** Recover an access token on app boot when only a refresh token is stored. */
export async function bootstrapSession() {
  if (!getAccess() && getRefresh()) {
    try {
      await refreshAccess()
    } catch {
      clearSession()
    }
  }
}

export default api
