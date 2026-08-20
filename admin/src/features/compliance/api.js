import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// ── Global retention policy (read: any admin; write: super-admin) ────────────
export function useRetention() {
  return useQuery({
    queryKey: ['retention'],
    queryFn: async () => (await api.get('/compliance/retention')).data,
  })
}

export function useUpdateRetention() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (patch) => (await api.patch('/compliance/retention', patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['retention'] }),
  })
}

// ── Per-merchant compliance ──────────────────────────────────────────────────
export function useConsent(merchantId) {
  return useQuery({
    queryKey: ['consent', merchantId],
    queryFn: async () => (await api.get(`/merchants/${merchantId}/consent`)).data,
    enabled: Boolean(merchantId),
  })
}

export function useEraseMerchant(merchantId) {
  return useMutation({
    // DELETE with a body — the typed-slug confirmation + reason.
    mutationFn: async (body) =>
      (await api.delete(`/merchants/${merchantId}/erase`, { data: body })).data,
  })
}

// Full data-subject export as a JSON bundle (authenticated blob download).
export async function downloadMerchantExport(merchantId, slug) {
  const res = await api.get(`/merchants/${merchantId}/export`, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `merchant_${slug || merchantId}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
