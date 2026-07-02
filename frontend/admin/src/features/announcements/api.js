import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useAnnouncements() {
  return useQuery({
    queryKey: ['announcements'],
    queryFn: async () => (await api.get('/announcements')).data,
  })
}

export function useAudiencePreview(audience, param) {
  return useQuery({
    queryKey: ['audience-preview', audience, param],
    queryFn: async () =>
      (await api.get('/announcements/audience-preview', { params: { audience, param } })).data,
    enabled: Boolean(audience),
  })
}

export function useCreateAnnouncement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/announcements', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['announcements'] }),
  })
}

export function useSendAnnouncement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.post(`/announcements/${id}/send`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['announcements'] }),
  })
}

export function useDeleteAnnouncement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/announcements/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['announcements'] }),
  })
}
