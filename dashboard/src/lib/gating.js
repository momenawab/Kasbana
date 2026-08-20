// Global gating store (spec §12). A dependency-free subscribable so any locked
// control, usePlan guard, or a server PLAN_LIMIT response can open the
// UpgradeDrawer from anywhere. Snapshot is a cached object (stable reference)
// so useSyncExternalStore doesn't loop.
let _snapshot = { open: false, feature: null }
const listeners = new Set()

function set(next) {
  _snapshot = next
  listeners.forEach((l) => l())
}

export const gating = {
  open(feature) {
    set({ open: true, feature: feature || null })
  },
  close() {
    set({ open: false, feature: null })
  },
  subscribe(fn) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
  getSnapshot() {
    return _snapshot
  },
}
