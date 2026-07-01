import { Routes, Route, Navigate } from 'react-router-dom'
import RequireAuth from './layout/RequireAuth'
import AdminShell from './layout/AdminShell'
import Login from './features/auth/Login'
import Home from './features/home/Home'
import MerchantsList from './features/merchants/MerchantsList'
import MerchantDetail from './features/merchants/MerchantDetail'
import PlansList from './features/plans/PlansList'
import BillingHome from './features/billing/BillingHome'

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
        <Route path="/merchants" element={<MerchantsList />} />
        <Route path="/merchants/:id" element={<MerchantDetail />} />
        <Route path="/plans" element={<PlansList />} />
        <Route path="/billing" element={<BillingHome />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
