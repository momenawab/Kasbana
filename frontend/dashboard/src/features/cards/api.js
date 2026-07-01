// Card data hooks (spec §6 /cards). List/create/detail are live backend (1.3);
// stats/qr are 1.6 (mock until the backend prod promotion).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useCards() {
  return useQuery({
    queryKey: ['cards'],
    queryFn: async () => (await api.get('/cards')).data.results ?? [],
  })
}

export function useCard(id) {
  return useQuery({
    queryKey: ['cards', id],
    queryFn: async () => (await api.get(`/cards/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useCardStats(id) {
  return useQuery({
    queryKey: ['cards', id, 'stats'],
    queryFn: async () => (await api.get(`/cards/${id}/stats`)).data,
    enabled: Boolean(id),
  })
}

export function useSaveCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }) =>
      id
        ? (await api.patch(`/cards/${id}`, body)).data
        : (await api.post('/cards', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cards'] }),
  })
}
