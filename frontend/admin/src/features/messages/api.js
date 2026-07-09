import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useMessages() {
  return useQuery({
    queryKey: ['messages'],
    queryFn: async () => (await api.get('/messages')).data,
  })
}

export function useUpdateMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, status }) => (await api.patch(`/messages/${id}`, { status })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['messages'] }),
  })
}

export function useDeleteMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/messages/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['messages'] }),
  })
}

export function useReplyMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, message }) =>
      (await api.post(`/messages/${id}/reply`, { message })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['messages'] }),
  })
}

export function useCreateMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => (await api.post('/messages', payload)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['messages'] }),
  })
}
