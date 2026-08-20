import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// ── health ───────────────────────────────────────────────────────────────────
export function useHealth() {
  return useQuery({
    queryKey: ['ops-health'],
    queryFn: async () => (await api.get('/ops/health')).data,
    refetchInterval: 15000, // live-ish
  })
}

// ── feature flags ──────────────────────────────────────────────────────────────
export function useFlags() {
  return useQuery({
    queryKey: ['ops-flags'],
    queryFn: async () => (await api.get('/ops/flags')).data,
  })
}

function useFlagMutation(mutationFn) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-flags'] }),
  })
}

export const useCreateFlag = () =>
  useFlagMutation(async (body) => (await api.post('/ops/flags', body)).data)
export const useUpdateFlag = () =>
  useFlagMutation(async ({ key, patch }) => (await api.patch(`/ops/flags/${key}`, patch)).data)
export const useSetOverride = () =>
  useFlagMutation(
    async ({ key, body }) => (await api.post(`/ops/flags/${key}/override`, body)).data
  )
export const useClearOverride = () =>
  useFlagMutation(
    async ({ key, merchant_id }) =>
      (await api.delete(`/ops/flags/${key}/override`, { data: { merchant_id } })).data
  )

// ── settings + maintenance ─────────────────────────────────────────────────────
export function useSettings() {
  return useQuery({
    queryKey: ['ops-settings'],
    queryFn: async () => (await api.get('/ops/settings')).data,
  })
}

export function useUpsertSetting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ key, body }) => (await api.patch(`/ops/settings/${key}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-settings'] }),
  })
}

export function useMaintenance() {
  return useQuery({
    queryKey: ['ops-maintenance'],
    queryFn: async () => (await api.get('/ops/maintenance')).data,
  })
}

export function useSetMaintenance() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.patch('/ops/maintenance', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-maintenance'] }),
  })
}

// ── task monitor ───────────────────────────────────────────────────────────────
export function useTasks(status) {
  return useQuery({
    queryKey: ['ops-tasks', status],
    queryFn: async () => (await api.get('/ops/tasks', { params: status ? { status } : {} })).data,
  })
}

export function useRetryTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (taskId) => (await api.post(`/ops/tasks/${taskId}/retry`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-tasks'] }),
  })
}

// ── webhook deliveries ───────────────────────────────────────────────────────
export function useWebhooks(params) {
  return useQuery({
    queryKey: ['ops-webhooks', params],
    queryFn: async () => (await api.get('/ops/webhooks', { params })).data,
  })
}

export function useReplayWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.post(`/ops/webhooks/${id}/replay`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-webhooks'] }),
  })
}

// ── wallet sync failures ───────────────────────────────────────────────────────
export function useWalletFailures(resolved) {
  return useQuery({
    queryKey: ['ops-wallet-failures', resolved],
    queryFn: async () =>
      (await api.get('/ops/wallet-failures', { params: resolved != null ? { resolved } : {} }))
        .data,
  })
}

export function useReprovision() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.post(`/ops/wallet-failures/${id}/reprovision`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ops-wallet-failures'] }),
  })
}
