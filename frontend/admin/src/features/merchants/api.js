import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useMerchants(params) {
  return useQuery({
    queryKey: ['merchants', params],
    queryFn: async () => (await api.get('/merchants', { params })).data,
    keepPreviousData: true,
  })
}

export function useMerchant(id) {
  return useQuery({
    queryKey: ['merchant', id],
    queryFn: async () => (await api.get(`/merchants/${id}`)).data,
    enabled: Boolean(id),
  })
}

// Edit a merchant's core profile (name / legal name / business contact).
export function useUpdateMerchant(id) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.patch(`/merchants/${id}`, body)).data,
    onSuccess: (data) => {
      // Seed the detail cache with the server's fresh payload, then refresh the
      // list so the directory row picks up the new name.
      qc.setQueryData(['merchant', id], data)
      qc.invalidateQueries({ queryKey: ['merchants'] })
    },
  })
}

export function useSubscription(merchantId) {
  return useQuery({
    queryKey: ['subscription', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/subscription`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useSubscriptionAudit(merchantId) {
  return useQuery({
    queryKey: ['subscription-audit', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/subscription/audit`)).data,
    enabled: Boolean(merchantId),
  })
}

function useSubscriptionMutation(merchantId, path) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) =>
      (await api.post(`/merchants/${merchantId}/subscription${path}`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscription', merchantId] })
      qc.invalidateQueries({ queryKey: ['subscription-audit', merchantId] })
    },
  })
}

export function useUpdateSubscription(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) =>
      (await api.patch(`/merchants/${merchantId}/subscription`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscription', merchantId] })
      qc.invalidateQueries({ queryKey: ['subscription-audit', merchantId] })
    },
  })
}

export function useExtendTrial(merchantId) {
  return useSubscriptionMutation(merchantId, '/extend-trial')
}

export function useSetComp(merchantId) {
  return useSubscriptionMutation(merchantId, '/comp')
}

export function useLockSubscription(merchantId) {
  return useSubscriptionMutation(merchantId, '/lock')
}

export function useUnlockSubscription(merchantId) {
  return useSubscriptionMutation(merchantId, '/unlock')
}

// ── Support tools & impersonation (Phase 6) ─────────────────────────────────
export function useActivity(merchantId) {
  return useQuery({
    queryKey: ['activity', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/activity`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useSupportNotes(merchantId) {
  return useQuery({
    queryKey: ['support-notes', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/support/notes`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useAddSupportNote(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) =>
      (await api.post(`/merchants/${merchantId}/support/notes`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['support-notes', merchantId] }),
  })
}

export function useImpersonations(merchantId) {
  return useQuery({
    queryKey: ['impersonations', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/impersonations`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useStartImpersonation(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post(`/merchants/${merchantId}/impersonate`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['impersonations', merchantId] }),
  })
}

function useSupportAction(merchantId, path) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) =>
      (await api.post(`/merchants/${merchantId}/support/${path}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['activity', merchantId] }),
  })
}

export function useSendPasswordReset(merchantId) {
  return useSupportAction(merchantId, 'send-password-reset')
}

export function useResendInvite(merchantId) {
  return useSupportAction(merchantId, 'resend-invite')
}

export function useClearStuckCheckout(merchantId) {
  return useSupportAction(merchantId, 'clear-stuck-checkout')
}

// Messages this merchant sent from its dashboard support form.
export function useMerchantMessages(merchantId) {
  return useQuery({
    queryKey: ['merchant-messages', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/support/messages`)).data,
    enabled: Boolean(merchantId),
  })
}

// Reply reuses the global message endpoint but refreshes this merchant's thread.
export function useReplyMerchantMessage(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, message }) =>
      (await api.post(`/messages/${id}/reply`, { message })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['merchant-messages', merchantId] }),
  })
}
