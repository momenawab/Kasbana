// Plan gating (spec §12). Reads entitlements from the /me query.
// Returns {plan, can(feature), limit(key), usage(key), atLimit(key)}.
import { useMe } from './useAuth'

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

  return { plan: ent?.plan ?? null, entitlements: ent, can, limit, usage, atLimit }
}
