// Cashier scan data hooks (POST /loyalty/scan + the loyalty engine).
// scan resolves a wallet QR payload -> CardState; stamp/redeem are the live
// loyalty engine (1.2). No react-query cache: each scan is a fresh till action.
import { useMutation } from '@tanstack/react-query'
import api, { idempotent } from '../../lib/api'

export function useScanActions() {
  const resolve = useMutation({
    mutationFn: async (code) => (await api.post('/loyalty/scan', { code })).data,
  })
  const stamp = useMutation({
    mutationFn: async ({ customerCardId, delta = 1, force = false }) =>
      (
        await api.post(
          '/loyalty/stamp',
          // Coerce force to a real boolean: a stray truthy value (e.g. a click
          // event passed as the arg) would otherwise crash JSON serialization
          // and surface as a bogus "network error".
          { customer_card_id: customerCardId, delta, force: Boolean(force) },
          idempotent()
        )
      ).data,
  })
  const redeem = useMutation({
    mutationFn: async ({ customerCardId, rewardId }) =>
      (
        await api.post(
          '/loyalty/redeem',
          { customer_card_id: customerCardId, reward_id: rewardId },
          idempotent()
        )
      ).data,
  })
  return { resolve, stamp, redeem }
}
