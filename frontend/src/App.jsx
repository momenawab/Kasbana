import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Home from './pages/Home.jsx'
import Support from './pages/Support.jsx'
import Privacy from './pages/Privacy.jsx'
import GetStarted from './pages/GetStarted.jsx'
import NotFound from './pages/NotFound.jsx'

export default function App() {
  return (
    <Routes>
      {/* English site at "/" */}
      <Route path="/" element={<Layout lang="en" />}>
        <Route index element={<Home />} />
        <Route path="support" element={<Support />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="get-started" element={<GetStarted />} />
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* Arabic site at "/ar" */}
      <Route path="/ar" element={<Layout lang="ar" />}>
        <Route index element={<Home />} />
        <Route path="support" element={<Support />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="get-started" element={<GetStarted />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
