import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export function useCoupons() {
  return useQuery({
    queryKey: ['coupons'],
    queryFn: async () => (await api.get('/coupons')).data,
  })
}

export function useCouponRedemptions(code) {
  return useQuery({
    queryKey: ['coupon-redemptions', code],
    queryFn: async () => (await api.get(`/coupons/${code}/redemptions`)).data,
    enabled: Boolean(code),
  })
}

export function useCreateCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/coupons', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupons'] }),
  })
}

export function useUpdateCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ code, patch }) => (await api.patch(`/coupons/${code}`, patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupons'] }),
  })
}

// Apply a grantable coupon (trial-extension / free-months) to a merchant.
export function useApplyCouponToMerchant(merchantId) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (code) =>
      (await api.post(`/merchants/${merchantId}/apply-coupon`, { code })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['merchant', merchantId] })
      qc.invalidateQueries({ queryKey: ['subscription', merchantId] })
    },
  })
}
