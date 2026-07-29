// Entitlement stand-in for the Wallet Studio.
//
// The copied editor gates its rich controls on the merchant's `custom_branding`
// entitlement (free plans keep the smart defaults). That gate is meaningless
// here: the platform authoring a card *for* a merchant is not the merchant
// buying a feature, and the admin endpoint deliberately skips the entitlement
// check too (see console/views_wallet_studio.py). So every capability reads as
// granted, and the editor renders unlocked.
// Mirrors the subset of the dashboard hook's surface the editor uses:
// `can(feature)` and `requireFeature(feature)`.
export function usePlan() {
  return {
    plan: null,
    entitlements: null,
    can: () => true,
    limit: () => null,
    usage: () => 0,
    atLimit: () => false,
    requireFeature: () => true,
    requireRoom: () => true,
  }
}
