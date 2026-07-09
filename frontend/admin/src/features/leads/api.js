import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useLeads() {
  return useQuery({
    queryKey: ['leads'],
    queryFn: async () => (await api.get('/leads')).data,
  })
}

export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, status }) => (await api.patch(`/leads/${id}`, { status })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
  })
}

export function useDeleteLead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/leads/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
  })
}
