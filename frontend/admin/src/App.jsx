import { Routes, Route, Navigate } from 'react-router-dom'
import RequireAuth from './layout/RequireAuth'
import AdminShell from './layout/AdminShell'
import Login from './features/auth/Login'
import Home from './features/home/Home'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <AdminShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Home />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
