// Plan gating (spec §12). Reads entitlements from the /me query.
// Returns {plan, can, limit, usage, atLimit, requireFeature, requireRoom}.
import { useMe } from './useAuth'
import { gating } from '../lib/gating'

export function usePlan() {
  const { data } = useMe()
  const ent = data?.entitlements ?? null

  const can = (feature) => Boolean(ent?.features?.[feature])
  const limit = (key) => ent?.limits?.[key] ?? null // null = unlimited
  const usage = (key) => ent?.usage?.[key] ?? 0
  const atLimit = (key) => {
    const max = limit(key)
    if (max == null) return false
    return usage(key.replace('max_', '')) >= max
  }

  // Guards: return true if allowed; otherwise open the UpgradeDrawer and return false.
  const requireFeature = (feature) => {
    if (can(feature)) return true
    gating.open(feature)
    return false
  }
  const requireRoom = (key) => {
    if (!atLimit(key)) return true
    gating.open(key)
    return false
  }

  return {
    plan: ent?.plan ?? null,
    entitlements: ent,
    can,
    limit,
    usage,
    atLimit,
    requireFeature,
    requireRoom,
  }
}
