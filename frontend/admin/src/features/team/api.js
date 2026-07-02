import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useAdmins() {
  return useQuery({
    queryKey: ['admins'],
    queryFn: async () => (await api.get('/admins')).data,
  })
}

export function useRbacMatrix() {
  return useQuery({
    queryKey: ['rbac-matrix'],
    queryFn: async () => (await api.get('/rbac/matrix')).data,
  })
}

export function useAdminActivity(id) {
  return useQuery({
    queryKey: ['admin-activity', id],
    queryFn: async () => (await api.get(`/admins/${id}/activity`)).data,
    enabled: Boolean(id),
  })
}

export function useInviteAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/admins', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admins'] }),
  })
}

export function useUpdateAdmin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, patch }) => (await api.patch(`/admins/${id}`, patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admins'] }),
  })
}
