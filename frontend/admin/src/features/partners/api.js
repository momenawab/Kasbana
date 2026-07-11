import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// Partners are cursor-paginated on the server; unwrap to the results array.
export function usePartners() {
  return useQuery({
    queryKey: ['partners'],
    queryFn: async () => (await api.get('/partners')).data.results ?? [],
  })
}

export function usePartnerReferrals(id) {
  return useQuery({
    queryKey: ['partner-referrals', id],
    queryFn: async () => (await api.get(`/partners/${id}/referrals`)).data,
    enabled: Boolean(id),
  })
}

export function useProgramConfig() {
  return useQuery({
    queryKey: ['partner-config'],
    queryFn: async () => (await api.get('/partner-config')).data,
  })
}

export function useSaveProgramConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch) => (await api.patch('/partner-config', patch)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['partner-config'] })
      qc.invalidateQueries({ queryKey: ['partners'] })
    },
  })
}

export function useCreatePartner() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/partners', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['partners'] }),
  })
}

export function useUpdatePartner() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, patch }) => (await api.patch(`/partners/${id}`, patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['partners'] }),
  })
}

export function useDeletePartner() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/partners/${id}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['partners'] }),
  })
}

export function useAssignReferral(partnerId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (merchantId) =>
      (await api.post(`/partners/${partnerId}/referrals`, { merchant_id: merchantId })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['partner-referrals', partnerId] })
      qc.invalidateQueries({ queryKey: ['partners'] })
    },
  })
}
