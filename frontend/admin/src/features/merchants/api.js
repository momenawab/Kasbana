import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'

export function useMerchants(params) {
  return useQuery({
    queryKey: ['merchants', params],
    queryFn: async () => (await api.get('/merchants', { params })).data,
    keepPreviousData: true,
  })
}

export function useMerchant(id) {
  return useQuery({
    queryKey: ['merchant', id],
    queryFn: async () => (await api.get(`/merchants/${id}`)).data,
    enabled: Boolean(id),
  })
}
