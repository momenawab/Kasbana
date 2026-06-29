// Single axios instance + auth helpers (spec §5).
// - request interceptor attaches Bearer access
// - response interceptor: on 401 refresh once + retry, else log out
// - error envelope {error:{code,message,fields}} surfaced via normalizeError()
import axios from 'axios'
import { clearSession, getAccess, getRefresh, setAccess, setTokens } from './auth'
import { queryClient } from './queryClient'

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
    return Promise.reject(error)
  }
)

/** Turn an axios error into the contract envelope shape for callers/forms. */
export function normalizeError(error) {
  const body = error?.response?.data?.error
  return {
    code: body?.code || 'SERVER_ERROR',
    message: body?.message || 'Something went wrong.',
    fields: body?.fields || null,
  }
}

export async function login(email, password) {
  const { data } = await api.post('/auth/token', { email, password })
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
