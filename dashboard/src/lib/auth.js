// Token store: access in memory, refresh in localStorage. No axios here (keeps
// this import-cycle-free; api.js depends on it, not the reverse).
//
// Impersonation (admin "view as merchant", Phase 6): a short-lived access token
// handed off via the URL fragment, kept in sessionStorage so it never outlives
// the tab and never mixes with a real session. While impersonating there is NO
// refresh token — the session hard-stops at the token's expiry (or earlier if
// the admin ends it server-side).
const REFRESH_KEY = 'stampn_refresh'
const IMP_KEY = 'stampn_impersonation'

let accessToken = null

export function getAccess() {
  return sessionStorage.getItem(IMP_KEY) || accessToken
}

export function getRefresh() {
  return localStorage.getItem(REFRESH_KEY)
}

export function setAccess(access) {
  accessToken = access || null
}

export function setTokens({ access, refresh }) {
  accessToken = access || null
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearSession() {
  accessToken = null
  localStorage.removeItem(REFRESH_KEY)
  sessionStorage.removeItem(IMP_KEY)
}

// ── impersonation ─────────────────────────────────────────────────────────────
export function startImpersonation(token) {
  sessionStorage.setItem(IMP_KEY, token)
}

export function isImpersonating() {
  return Boolean(sessionStorage.getItem(IMP_KEY))
}

export function endImpersonation() {
  sessionStorage.removeItem(IMP_KEY)
}

/** A session exists if we hold a refresh token (access is recovered via
 * refresh) — or an impersonation token (no refresh by design). */
export function hasSession() {
  return Boolean(getRefresh()) || isImpersonating()
}
