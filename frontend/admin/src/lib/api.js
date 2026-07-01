// Admin API client — talks to /api/admin/v1 with the admin bearer token.
// On a 401 it tries a one-shot refresh, then forces re-login.
import axios from 'axios'
import { getAccess, getRefresh, setAccess, clearTokens } from './auth'

const BASE = (import.meta.env.VITE_API_URL || '') + '/api/admin/v1'

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use((config) => {
  const token = getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshing = null

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    const refresh = getRefresh()
    if (status === 401 && refresh && !original._retried) {
      original._retried = true
      try {
        refreshing =
          refreshing ||
          axios.post(`${BASE}/auth/refresh`, { refresh }).finally(() => {
            refreshing = null
          })
        const { data } = await refreshing
        setAccess(data.access)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        clearTokens()
        if (location.pathname !== '/login') location.assign('/login')
      }
    }
    if (status === 401) {
      clearTokens()
      if (location.pathname !== '/login') location.assign('/login')
    }
    return Promise.reject(error)
  }
)

// Extract the API error envelope { error: { code, message } } into a flat shape.
export function normalizeError(err) {
  const e = err?.response?.data?.error
  return {
    code: e?.code || 'ERROR',
    message: e?.message || err?.message || 'Something went wrong.',
    fields: e?.fields || {},
  }
}

export default api
