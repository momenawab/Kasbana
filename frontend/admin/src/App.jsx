import { Routes, Route, Navigate } from 'react-router-dom'
import RequireAuth from './layout/RequireAuth'
import AdminShell from './layout/AdminShell'
import Login from './features/auth/Login'
import Home from './features/home/Home'
import MerchantsList from './features/merchants/MerchantsList'
import MerchantDetail from './features/merchants/MerchantDetail'
import PlansList from './features/plans/PlansList'
import BillingHome from './features/billing/BillingHome'
import RevenueHome from './features/revenue/RevenueHome'
import PlatformHome from './features/platform/PlatformHome'
import LifecycleHome from './features/lifecycle/LifecycleHome'
import AnnouncementsHome from './features/announcements/AnnouncementsHome'
import PromotionsHome from './features/promotions/PromotionsHome'
import TeamHome from './features/team/TeamHome'

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
        <Route path="/revenue" element={<RevenueHome />} />
        <Route path="/platform" element={<PlatformHome />} />
        <Route path="/lifecycle" element={<LifecycleHome />} />
        <Route path="/announcements" element={<AnnouncementsHome />} />
        <Route path="/promotions" element={<PromotionsHome />} />
        <Route path="/team" element={<TeamHome />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
