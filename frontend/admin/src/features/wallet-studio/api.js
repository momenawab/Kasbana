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
      // The scaffold renders the SAVED design, so an Editor save changes it.
      // Without this the JSON tab would keep offering the pre-edit pass.
      qc.invalidateQueries({ queryKey: ['wallet-studio', merchantId, cardId, 'scaffold'] })
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

/**
 * The card's pass as it renders today, in token-preserving form with the locked
 * keys removed — the starting point for a card that was built in the Editor and
 * has no overlay yet. Reflects the SAVED design, so it is refetched after a save.
 */
export function usePassScaffold(merchantId, cardId) {
  return useQuery({
    queryKey: ['wallet-studio', merchantId, cardId, 'scaffold'],
    queryFn: async () =>
      (await api.get(`/merchants/${merchantId}/cards/${cardId}/pass-scaffold`)).data,
    enabled: Boolean(merchantId && cardId),
  })
}

/**
 * The whole card as one document — {card, design, apple_overlay, google_overlay}
 * plus read-only {platform, assets}. Everything that shapes the card in one place,
 * so an admin doesn't have to know which row a given knob lives in.
 */
export function useCardJson(merchantId, cardId) {
  return useQuery({
    queryKey: ['wallet-studio', merchantId, cardId, 'card-json'],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/cards/${cardId}/card-json`)).data,
    enabled: Boolean(merchantId && cardId),
  })
}

export function useSaveCardJson(merchantId, cardId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (document) =>
      (await api.put(`/merchants/${merchantId}/cards/${cardId}/card-json`, document)).data,
    onSuccess: (data) => {
      qc.setQueryData(['wallet-studio', merchantId, cardId, 'card-json'], data)
      // A card-json save can move anything — the rail, the Editor's design and
      // the scaffold are all downstream of it.
      qc.invalidateQueries({ queryKey: ['wallet-studio', merchantId] })
    },
  })
}

/** Push the saved design to every live pass on this card. Deliberately manual. */
export function useRepublish(merchantId, cardId) {
  return useMutation({
    mutationFn: async () =>
      (await api.post(`/merchants/${merchantId}/cards/${cardId}/republish`, {})).data,
  })
}
