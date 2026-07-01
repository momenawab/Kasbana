// Location data hooks. List/create live (1.3); patch/stats are 1.6 (graceful).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: async () => (await api.get('/locations')).data.results ?? [],
  })
}

export function useSaveLocation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...body }) =>
      id
        ? (await api.patch(`/locations/${id}`, body)).data
        : (await api.post('/locations', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['locations'] }),
  })
}
