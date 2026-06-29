import { Navigate, useLocation } from 'react-router-dom'
import { hasSession } from '../lib/auth'

/** Guards protected routes — no session → /login?next=<path>. */
export default function RequireAuth({ children }) {
  const location = useLocation()
  if (!hasSession()) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children
}
