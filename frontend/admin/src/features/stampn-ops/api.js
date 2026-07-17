import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

const root = '/stampn-ops'

export const useOpsDashboard = () =>
  useQuery({ queryKey: ['stampn-ops', 'dashboard'], queryFn: () => api.get(`${root}/dashboard`).then((r) => r.data), refetchInterval: 30_000 })

export const useOpsAlerts = (status = 'open') =>
  useQuery({ queryKey: ['stampn-ops', 'alerts', status], queryFn: () => api.get(`${root}/alerts`, { params: { status } }).then((r) => r.data), refetchInterval: 30_000 })

export const useOpsSettings = () =>
  useQuery({ queryKey: ['stampn-ops', 'settings'], queryFn: () => api.get(`${root}/settings`).then((r) => r.data) })

export const useSaveOpsSettings = () => {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (body) => api.patch(`${root}/settings`, body).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['stampn-ops'] }) })
}

export const useTestTelegram = () => useMutation({ mutationFn: () => api.post(`${root}/telegram/test`).then((r) => r.data) })
export const useRefreshOps = () => {
  const qc = useQueryClient()
  return useMutation({ mutationFn: () => api.post(`${root}/refresh`).then((r) => r.data), onSuccess: () => qc.invalidateQueries({ queryKey: ['stampn-ops'] }) })
}
