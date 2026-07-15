// Customer data hooks (spec §6 /customers). List is live (1.3 + 1.6 filters);
// detail/timeline/message/delete are 1.6/1.7 (graceful until backend promotion).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api, { idempotent } from '../../lib/api'

export function useCustomers(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  ).toString()
  return useQuery({
    queryKey: ['customers', params],
    queryFn: async () => (await api.get(`/customers${qs ? `?${qs}` : ''}`)).data,
  })
}

// Server-side CSV export (Phase 3). Streams the *full* filtered customer book
// (not just the loaded page) and is gated by the `export` entitlement server-side.
// NB: responseType 'blob' means the api interceptor can't read a JSON error body,
// so the caller must handle a 402 (PLAN_LIMIT) itself. Returns a Blob to download.
export async function exportCustomersCsv(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  ).toString()
  const res = await api.get(`/customers/export${qs ? `?${qs}` : ''}`, { responseType: 'blob' })
  return res.data
}

export function useCustomer(id) {
  return useQuery({
    queryKey: ['customers', id],
    queryFn: async () => (await api.get(`/customers/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useTimeline(id) {
  return useQuery({
    queryKey: ['customers', id, 'timeline'],
    queryFn: async () => {
      try {
        return (await api.get(`/customers/${id}/timeline`)).data.results ?? []
      } catch {
        return []
      }
    },
    enabled: Boolean(id),
  })
}

export function useStampActions(id) {
  const qc = useQueryClient()
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['customers', id] })
    qc.invalidateQueries({ queryKey: ['customers', id, 'timeline'] })
  }
  const stamp = useMutation({
    mutationFn: async (delta) =>
      (await api.post('/loyalty/stamp', { customer_card_id: id, delta }, idempotent())).data,
    onSuccess: invalidate,
  })
  const redeem = useMutation({
    mutationFn: async (rewardId) =>
      (await api.post('/loyalty/redeem', { customer_card_id: id, reward_id: rewardId }, idempotent()))
        .data,
    onSuccess: invalidate,
  })
  const message = useMutation({
    mutationFn: async ({ channel, text }) =>
      (await api.post(`/customers/${id}/message`, { channel, text })).data,
  })
  const remove = useMutation({
    mutationFn: async () => (await api.delete(`/customers/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
  })
  return { stamp, redeem, message, remove }
}
