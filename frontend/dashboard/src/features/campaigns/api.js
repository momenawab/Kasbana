// Engage data hooks (spec §6). All 1.7 backend — graceful empty until promotion.
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

const safe = async (fn, fallback) => {
  try {
    return await fn()
  } catch {
    return fallback
  }
}

export function useCampaigns() {
  return useQuery({
    queryKey: ['campaigns'],
    queryFn: () => safe(async () => (await api.get('/campaigns')).data.results ?? [], []),
  })
}

export function useSegments() {
  return useQuery({
    queryKey: ['segments'],
    queryFn: () => safe(async () => (await api.get('/segments')).data.results ?? [], []),
  })
}

export function useCreateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/campaigns', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['campaigns'] }),
  })
}

export function useAutomations() {
  return useQuery({
    queryKey: ['automations'],
    queryFn: () => safe(async () => (await api.get('/automations')).data.results ?? [], []),
  })
}

export function useUpdateAutomation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ key, ...body }) => (await api.patch(`/automations/${key}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })
}
