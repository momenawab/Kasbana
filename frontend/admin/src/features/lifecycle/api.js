import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function usePipeline() {
  return useQuery({
    queryKey: ['lifecycle-pipeline'],
    queryFn: async () => (await api.get('/lifecycle/pipeline')).data,
  })
}

export function useAtRisk() {
  return useQuery({
    queryKey: ['lifecycle-at-risk'],
    queryFn: async () => (await api.get('/lifecycle/at-risk')).data,
  })
}

export function useModerationQueue(status = 'pending') {
  return useQuery({
    queryKey: ['moderation-flags', status],
    queryFn: async () => (await api.get('/moderation/flags', { params: { status } })).data,
  })
}

export function useRunScan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post('/moderation/scan')).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['moderation-flags'] }),
  })
}

export function useResolveFlag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, action, notes }) =>
      (await api.post(`/moderation/flags/${id}/resolve`, { action, notes })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['moderation-flags'] }),
  })
}

export function useSuspendMerchant(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ suspend, reason }) =>
      (await api.post(`/merchants/${merchantId}/${suspend ? 'suspend' : 'unsuspend'}`, { reason }))
        .data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['merchant', merchantId] })
      qc.invalidateQueries({ queryKey: ['lifecycle-pipeline'] })
    },
  })
}
