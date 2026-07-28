import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useDemoCards() {
  return useQuery({
    queryKey: ['demo-cards'],
    queryFn: async () => (await api.get('/demo-cards')).data,
  })
}

export function useCreateDemoCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/demo-cards', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['demo-cards'] }),
  })
}

// Re-fetch the add-to-wallet URLs for a card built earlier (they are generated
// on demand, not stored).
export function useDemoCardPass(cardId) {
  return useQuery({
    queryKey: ['demo-card-pass', cardId],
    queryFn: async () => (await api.get(`/demo-cards/${cardId}/pass`)).data,
    enabled: Boolean(cardId),
  })
}

export function useDeleteDemoCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (cardId) => (await api.delete(`/demo-cards/${cardId}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['demo-cards'] }),
  })
}
