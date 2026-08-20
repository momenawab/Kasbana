// Minimal toast bus for the admin console.
//
// The merchant dashboard has its own toast system and the Wallet Studio
// components copied from it call `useToast().success/error(...)`. Rather than
// port that stack, this is a small module-level pub/sub with the same call
// surface and no new dependency.
//
// The rendering half lives in components/Toaster.jsx — split so this file
// exports only non-components (React Fast Refresh requires that separation).
let nextId = 1
const listeners = new Set()

export function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function emit(tone, message) {
  const toast = { id: nextId++, tone, message: String(message ?? '') }
  listeners.forEach((fn) => fn(toast))
}

const api = {
  success: (message) => emit('success', message),
  error: (message) => emit('error', message),
}

export function useToast() {
  return api
}
