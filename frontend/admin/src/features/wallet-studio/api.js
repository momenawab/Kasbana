// Wallet Studio data hooks.
//
// The design endpoints mirror the merchant dashboard's (features/cards/api.js)
// but are nested under the merchant — the admin API is cross-tenant, so the
// merchant id in the path is what scopes a card to its owner. That is why every
// hook here takes `merchantId` where the dashboard's took only a card id.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

const designKey = (merchantId, cardId) => ['wallet-studio', merchantId, cardId, 'design']

export function useMerchantCards(merchantId) {
  return useQuery({
    queryKey: ['wallet-studio', merchantId, 'cards'],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/cards`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useWalletDesign(merchantId, cardId) {
  return useQuery({
    queryKey: designKey(merchantId, cardId),
    queryFn: async () =>
      (await api.get(`/merchants/${merchantId}/cards/${cardId}/wallet-design`)).data,
    enabled: Boolean(merchantId && cardId),
  })
}

export function useSaveWalletDesign(merchantId, cardId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) =>
      (await api.patch(`/merchants/${merchantId}/cards/${cardId}/wallet-design`, body)).data,
    onSuccess: (data) => {
      qc.setQueryData(designKey(merchantId, cardId), data)
      // The rail badges cards that carry an overlay — keep that truthful.
      qc.invalidateQueries({ queryKey: ['wallet-studio', merchantId, 'cards'] })
    },
  })
}

export function useWalletTemplates() {
  return useQuery({
    queryKey: ['wallet-studio', 'templates'],
    queryFn: async () => (await api.get('/wallet-studio/templates')).data,
    staleTime: Infinity,
  })
}

/**
 * Dry-run a design without saving it. `design` is the editor's current state, so
 * an admin sees the resolved pass — and any validation error — before committing.
 */
export function usePassPreview(merchantId, cardId) {
  return useMutation({
    mutationFn: async (body) =>
      (await api.post(`/merchants/${merchantId}/cards/${cardId}/pass-preview`, body ?? {})).data,
  })
}

/** Push the saved design to every live pass on this card. Deliberately manual. */
export function useRepublish(merchantId, cardId) {
  return useMutation({
    mutationFn: async () =>
      (await api.post(`/merchants/${merchantId}/cards/${cardId}/republish`, {})).data,
  })
}
