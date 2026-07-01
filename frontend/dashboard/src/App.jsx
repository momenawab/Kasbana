import { Routes, Route, Navigate } from 'react-router-dom'
import RequireAuth from './layout/RequireAuth'
import Shell from './layout/Shell'
import Login from './features/auth/Login'
import Signup from './features/auth/Signup'
import Forgot from './features/auth/Forgot'
import Reset from './features/auth/Reset'
import Invite from './features/auth/Invite'
import Enroll from './features/enroll/Enroll'
import Onboarding from './features/onboarding/Onboarding'
import Overview from './features/overview/Overview'
import Scan from './features/scan/Scan'
import CardsList from './features/cards/CardsList'
import CardDesigner from './features/cards/CardDesigner'
import CardDetail from './features/cards/CardDetail'
import Poster from './features/cards/Poster'
import EnrollQr from './features/cards/EnrollQr'
import CustomersList from './features/customers/CustomersList'
import CustomerProfile from './features/customers/CustomerProfile'
import Analytics from './features/analytics/Analytics'
import CampaignsList from './features/campaigns/CampaignsList'
import CampaignCompose from './features/campaigns/CampaignCompose'
import Automations from './features/campaigns/Automations'
import LocationsList from './features/locations/LocationsList'
import Team from './features/team/Team'
import Billing from './features/billing/Billing'
import Settings from './features/settings/Settings'
import Gallery from './routes/Gallery'

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/__gallery" element={<Gallery />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot" element={<Forgot />} />
      <Route path="/reset/:token" element={<Reset />} />
      <Route path="/invite/:token" element={<Invite />} />
      {/* Public customer enrollment page (QR target) — no login. */}
      <Route path="/enroll/:token" element={<Enroll />} />

      {/* Protected (inside Shell) */}
      <Route
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Overview />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/cards" element={<CardsList />} />
        <Route path="/cards/new" element={<CardDesigner />} />
        <Route path="/cards/:id" element={<CardDetail />} />
        <Route path="/cards/:id/edit" element={<CardDesigner />} />
        <Route path="/cards/:id/qr" element={<EnrollQr />} />
        <Route path="/cards/:id/poster" element={<Poster />} />
        <Route path="/customers" element={<CustomersList />} />
        <Route path="/customers/:id" element={<CustomerProfile />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/campaigns" element={<CampaignsList />} />
        <Route path="/campaigns/new" element={<CampaignCompose />} />
        <Route path="/automations" element={<Automations />} />
        <Route path="/locations" element={<LocationsList />} />
        <Route path="/locations/:id" element={<LocationsList />} />
        <Route path="/team" element={<Team />} />
        <Route path="/billing" element={<Billing />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/onboarding" element={<Onboarding />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
