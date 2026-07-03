import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useSessions() {
  return useQuery({
    queryKey: ['auth-sessions'],
    queryFn: async () => (await api.get('/auth/sessions')).data,
  })
}

export function useRevokeSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/auth/sessions/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-sessions'] }),
  })
}

export function useLogoutEverywhere() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.delete('/auth/sessions')).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-sessions'] }),
  })
}

// Voluntary MFA enrolment (already logged in): setup returns QR + secret,
// confirm verifies a code and flips it on.
export function useMfaSetup() {
  return useMutation({ mutationFn: async () => (await api.post('/auth/mfa/setup')).data })
}

export function useMfaConfirm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (code) => (await api.post('/auth/mfa/confirm', { code })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-me'] }),
  })
}

// Re-prove credentials to unlock a sensitive action for a short window.
export async function stepUp({ password, code }) {
  return (await api.post('/auth/step-up', { password, code })).data
}
