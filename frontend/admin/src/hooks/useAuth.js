// Admin session — GET /me (id, email, name, role, mfa_enabled).
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { hasSession, clearTokens } from '../lib/auth'

export function useMe() {
  return useQuery({
    queryKey: ['admin-me'],
    queryFn: async () => (await api.get('/me')).data,
    enabled: hasSession(),
  })
}

export function useAuth() {
  const me = useMe()
  return {
    isLoading: me.isLoading,
    admin: me.data ?? null,
    role: me.data?.role ?? null,
    logout: () => {
      clearTokens()
      location.assign('/login')
    },
  }
}
