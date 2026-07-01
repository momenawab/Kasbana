// Token store: access in memory, refresh in localStorage. No axios here (keeps
// this import-cycle-free; api.js depends on it, not the reverse).
const REFRESH_KEY = 'stampn_refresh'

let accessToken = null

export function getAccess() {
  return accessToken
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
}

/** A session exists if we hold a refresh token (access is recovered via refresh). */
export function hasSession() {
  return Boolean(getRefresh())
}
