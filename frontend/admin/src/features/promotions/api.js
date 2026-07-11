import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// `group` is optional: undefined = every coupon, 'none' = ungrouped only, or a
// group id to narrow to that group. Matches the backend ?group= filter.
export function useCoupons(group) {
  return useQuery({
    queryKey: ['coupons', group ?? 'all'],
    queryFn: async () =>
      (await api.get('/coupons', { params: group ? { group } : undefined })).data,
  })
}

// Coupon groups are cursor-paginated on the server; unwrap to the results array.
export function useCouponGroups() {
  return useQuery({
    queryKey: ['coupon-groups'],
    queryFn: async () => (await api.get('/coupon-groups')).data.results ?? [],
  })
}

export function useCreateCouponGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body) => (await api.post('/coupon-groups', body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupon-groups'] }),
  })
}

export function useUpdateCouponGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, patch }) => (await api.patch(`/coupon-groups/${id}`, patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coupon-groups'] }),
  })
}

export function useDeleteCouponGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/coupon-groups/${id}`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coupon-groups'] })
      qc.invalidateQueries({ queryKey: ['coupons'] })
    },
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
