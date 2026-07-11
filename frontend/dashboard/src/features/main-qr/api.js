// Main QR hooks (finalize Phase A) — GET/PATCH /settings/main-qr + rotate.
// One printed code for the whole merchant, re-pointed by electing another card.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useMainQr() {
  return useQuery({
    queryKey: ['main-qr'],
    queryFn: async () => (await api.get('/settings/main-qr')).data,
  })
}

export function useSetPrimaryCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (cardId) =>
      (await api.patch('/settings/main-qr', { primary_card_id: cardId })).data,
    onSuccess: (data) => qc.setQueryData(['main-qr'], data),
  })
}

export function useRotateMainQr() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post('/settings/main-qr/rotate')).data,
    onSuccess: (data) => qc.setQueryData(['main-qr'], data),
  })
}
