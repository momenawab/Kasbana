// Admin token storage — namespaced keys ("stampn.admin.*") so the console and
// the merchant dashboard never collide on a shared browser.
const ACCESS = 'stampn.admin.access'
const REFRESH = 'stampn.admin.refresh'

export function getAccess() {
  return localStorage.getItem(ACCESS)
}
export function getRefresh() {
  return localStorage.getItem(REFRESH)
}
export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem(ACCESS, access)
  if (refresh) localStorage.setItem(REFRESH, refresh)
}
export function setAccess(access) {
  if (access) localStorage.setItem(ACCESS, access)
}
export function clearTokens() {
  localStorage.removeItem(ACCESS)
  localStorage.removeItem(REFRESH)
}
export function hasSession() {
  return Boolean(getAccess())
}
