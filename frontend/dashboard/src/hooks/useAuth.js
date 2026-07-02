// Session context from GET /me (merchant + entitlements + staff role).
import { useQuery } from '@tanstack/react-query'
import api, { login as apiLogin, logout as apiLogout } from '../lib/api'
import { hasSession } from '../lib/auth'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get('/me')).data,
    enabled: hasSession(),
  })
}

export function useAuth() {
  const me = useMe()
  return {
    isLoading: me.isLoading,
    merchant: me.data?.merchant ?? null,
    entitlements: me.data?.entitlements ?? null,
    role: me.data?.staff?.role ?? null,
    impersonation: me.data?.impersonation ?? null,
    login: apiLogin,
    logout: apiLogout,
  }
}
