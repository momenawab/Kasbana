import { Routes, Route, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import RequireAuth from './layout/RequireAuth'
import Shell from './layout/Shell'
import Login from './features/auth/Login'
import Signup from './features/auth/Signup'
import Forgot from './features/auth/Forgot'
import Reset from './features/auth/Reset'
import Invite from './features/auth/Invite'
import Onboarding from './features/onboarding/Onboarding'
import CardsList from './features/cards/CardsList'
import CardDesigner from './features/cards/CardDesigner'
import CardDetail from './features/cards/CardDetail'
import EnrollQr from './features/cards/EnrollQr'
import Placeholder from './routes/Placeholder'
import Gallery from './routes/Gallery'

// Phase 1: real auth shell + routing; feature screens are placeholders that
// later phases replace (Cards = P4, Overview/Customers/Analytics = P5, etc.).
function Page({ tkey }) {
  const { t } = useTranslation()
  return <Placeholder title={t(tkey)} />
}

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

      {/* Protected (inside Shell) */}
      <Route
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Page tkey="nav.overview" />} />
        <Route path="/cards" element={<CardsList />} />
        <Route path="/cards/new" element={<CardDesigner />} />
        <Route path="/cards/:id" element={<CardDetail />} />
        <Route path="/cards/:id/edit" element={<CardDesigner />} />
        <Route path="/cards/:id/qr" element={<EnrollQr />} />
        <Route path="/customers" element={<Page tkey="nav.customers" />} />
        <Route path="/customers/:id" element={<Page tkey="nav.customers" />} />
        <Route path="/analytics" element={<Page tkey="nav.analytics" />} />
        <Route path="/campaigns" element={<Page tkey="nav.messaging" />} />
        <Route path="/campaigns/new" element={<Page tkey="nav.messaging" />} />
        <Route path="/automations" element={<Page tkey="nav.messaging" />} />
        <Route path="/locations" element={<Page tkey="nav.locations" />} />
        <Route path="/locations/:id" element={<Page tkey="nav.locations" />} />
        <Route path="/team" element={<Page tkey="nav.team" />} />
        <Route path="/billing" element={<Page tkey="nav.billing" />} />
        <Route path="/settings" element={<Page tkey="nav.settings" />} />
        <Route path="/onboarding" element={<Onboarding />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
