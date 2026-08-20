// Registration-theme (enroll page + QR) data hooks (finalize Phase 2).
// Merchant default:  GET/PATCH        /settings/enroll-theme
// Per-card override: GET/PATCH/DELETE /cards/{id}/enroll-theme
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

const merchantKey = ['enroll-theme', 'merchant']
const cardKey = (id) => ['enroll-theme', 'card', id]

function pathFor(cardId) {
  return cardId ? `/cards/${cardId}/enroll-theme` : '/settings/enroll-theme'
}

export function useEnrollTheme(cardId) {
  return useQuery({
    queryKey: cardId ? cardKey(cardId) : merchantKey,
    queryFn: async () => (await api.get(pathFor(cardId))).data,
  })
}

export function useSaveEnrollTheme(cardId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch) => (await api.patch(pathFor(cardId), patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: cardId ? cardKey(cardId) : merchantKey }),
  })
}

export function useClearCardEnrollTheme(cardId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.delete(`/cards/${cardId}/enroll-theme`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: cardKey(cardId) }),
  })
}
