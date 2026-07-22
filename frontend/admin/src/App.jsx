import { Routes, Route, Navigate } from 'react-router-dom'
import RequireAuth from './layout/RequireAuth'
import AdminShell from './layout/AdminShell'
import Login from './features/auth/Login'
import Home from './features/home/Home'
import LeadsHome from './features/leads/LeadsHome'
import LeadGenHome from './features/leadgen/LeadGenHome'
import LeadGenJobDetail from './features/leadgen/JobDetail'
import GeneratedLeadsHome from './features/leadgen/GeneratedLeadsHome'
import LeadDetail from './features/leads/LeadDetail'
import CrmSettings from './features/leads/CrmSettings'
import MessagesHome from './features/messages/MessagesHome'
import MerchantsList from './features/merchants/MerchantsList'
import MerchantDetail from './features/merchants/MerchantDetail'
import PlansList from './features/plans/PlansList'
import BillingHome from './features/billing/BillingHome'
import RevenueHome from './features/revenue/RevenueHome'
import PlatformHome from './features/platform/PlatformHome'
import LifecycleHome from './features/lifecycle/LifecycleHome'
import AnnouncementsHome from './features/announcements/AnnouncementsHome'
import PromotionsHome from './features/promotions/PromotionsHome'
import PartnersHome from './features/partners/PartnersHome'
import TeamHome from './features/team/TeamHome'
import AuditHome from './features/audit/AuditHome'
import ComplianceHome from './features/compliance/ComplianceHome'
import OpsHome from './features/ops/OpsHome'
import StampnOpsHome from './features/stampn-ops/StampnOpsHome'
import SecurityHome from './features/security/SecurityHome'

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
        <Route path="/leads" element={<LeadsHome />} />
        {/* Before /leads/:id — "settings" is not a lead id. */}
        <Route path="/leads/settings" element={<CrmSettings />} />
        <Route path="/leads/:id" element={<LeadDetail />} />
        <Route path="/leadgen" element={<LeadGenHome />} />
        {/* Before /leadgen/jobs/:id — "leads" is not a job id. */}
        <Route path="/leadgen/leads" element={<GeneratedLeadsHome />} />
        <Route path="/leadgen/jobs/:id" element={<LeadGenJobDetail />} />
        <Route path="/messages" element={<MessagesHome />} />
        <Route path="/merchants" element={<MerchantsList />} />
        <Route path="/merchants/:id" element={<MerchantDetail />} />
        <Route path="/plans" element={<PlansList />} />
        <Route path="/billing" element={<BillingHome />} />
        <Route path="/revenue" element={<RevenueHome />} />
        <Route path="/platform" element={<PlatformHome />} />
        <Route path="/lifecycle" element={<LifecycleHome />} />
        <Route path="/announcements" element={<AnnouncementsHome />} />
        <Route path="/promotions" element={<PromotionsHome />} />
        <Route path="/partners" element={<PartnersHome />} />
        <Route path="/team" element={<TeamHome />} />
        <Route path="/audit" element={<AuditHome />} />
        <Route path="/compliance" element={<ComplianceHome />} />
        <Route path="/ops" element={<OpsHome />} />
        <Route path="/stampn-ops" element={<StampnOpsHome />} />
        <Route path="/security" element={<SecurityHome />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
