import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function usePlans(includeArchived) {
  return useQuery({
    queryKey: ['plans', includeArchived],
    queryFn: async () =>
      (await api.get('/plans', includeArchived ? { params: { include_archived: 'true' } } : {}))
        .data,
  })
}

export function useSavePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ key, isNew, ...body }) =>
      isNew
        ? (await api.post('/plans', { key, ...body })).data
        : (await api.patch(`/plans/${key}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plans'] }),
  })
}
