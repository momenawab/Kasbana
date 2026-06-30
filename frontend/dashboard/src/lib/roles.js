// Role → area access, mirroring the backend (common/permissions.py).
// Owner/Admin do everything; Marketing owns engagement; Designer owns cards;
// Scanner is cashier-only. Areas: scan · insights · cards · engage · locations
// · team · billing. "Account settings" has no area — everyone manages their own.

export const AREAS_BY_ROLE = {
  OWNER: ['scan', 'insights', 'cards', 'engage', 'locations', 'team', 'billing'],
  ADMIN: ['scan', 'insights', 'cards', 'engage', 'locations', 'team', 'billing'],
  MARKETING: ['scan', 'insights', 'engage'],
  DESIGNER: ['scan', 'insights', 'cards'],
  SCANNER: ['scan'],
}

export const ROLES = ['OWNER', 'ADMIN', 'MARKETING', 'DESIGNER', 'SCANNER']

export function canAccess(role, area) {
  if (!area) return true // arealess screens (account settings) are open to all
  return (AREAS_BY_ROLE[role] || []).includes(area)
}

// Where a role lands after login: a cashier goes straight to the till.
export function landingFor(role) {
  return role === 'SCANNER' ? '/scan' : '/'
}

// Resolve a route path to its area (null = open to everyone).
const PATH_AREA = [
  ['/scan', 'scan'],
  ['/cards', 'cards'],
  ['/customers', 'engage'],
  ['/analytics', 'insights'],
  ['/campaigns', 'engage'],
  ['/automations', 'engage'],
  ['/locations', 'locations'],
  ['/team', 'team'],
  ['/billing', 'billing'],
]

export function areaForPath(pathname) {
  if (pathname === '/') return 'insights' // overview
  for (const [prefix, area] of PATH_AREA) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) return area
  }
  return null // settings, onboarding — open to all
}
