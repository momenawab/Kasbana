// Merchant support hooks (finalize Phase B) — GET/POST /support/messages.
// A logged-in merchant reaches the team; replies arrive by email.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useSupportMessages() {
  return useQuery({
    queryKey: ['support-messages'],
    queryFn: async () => (await api.get('/support/messages')).data,
  })
}

export function useSendSupportMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/support/messages', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['support-messages'] }),
  })
}
