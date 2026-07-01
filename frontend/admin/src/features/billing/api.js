import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useInvoices(params) {
  return useQuery({
    queryKey: ['invoices', params],
    queryFn: async () => (await api.get('/invoices', { params })).data,
    keepPreviousData: true,
  })
}

export function useInvoice(id) {
  return useQuery({
    queryKey: ['invoice', id],
    queryFn: async () => (await api.get(`/invoices/${id}`)).data,
    enabled: Boolean(id),
  })
}

export function useRetryInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.post(`/invoices/${id}/retry`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoices'] }),
  })
}

export function useCreateManualInvoice(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post(`/merchants/${merchantId}/invoices`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invoices'] }),
  })
}

export function useDunning() {
  return useQuery({
    queryKey: ['dunning'],
    queryFn: async () => (await api.get('/billing/dunning')).data,
  })
}

export function useNotifyDunning() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ merchantId, reason }) =>
      (await api.post(`/merchants/${merchantId}/dunning/notify`, { reason })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dunning'] }),
  })
}

export function useReconciliation() {
  return useQuery({
    queryKey: ['reconciliation'],
    queryFn: async () => (await api.get('/billing/reconciliation')).data,
  })
}
