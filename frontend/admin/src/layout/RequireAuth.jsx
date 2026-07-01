import { Navigate } from 'react-router-dom'
import { hasSession } from '../lib/auth'

/** No admin session → bounce to /login. */
export default function RequireAuth({ children }) {
  if (!hasSession()) return <Navigate to="/login" replace />
  return children
}
