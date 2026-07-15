import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'

// Lazy load pages for code splitting
const Home = lazy(() => import('./pages/Home.jsx'))
const Pricing = lazy(() => import('./pages/Pricing.jsx'))
const About = lazy(() => import('./pages/About.jsx'))
const Contact = lazy(() => import('./pages/Contact.jsx'))
const Support = lazy(() => import('./pages/Support.jsx'))
const Privacy = lazy(() => import('./pages/Privacy.jsx'))
const Refund = lazy(() => import('./pages/Refund.jsx'))
const GetStarted = lazy(() => import('./pages/GetStarted.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))

// A minimal fallback to show while the route chunks are loading.
// Since the layout is rendered immediately, this just needs to fill the content area.
const PageFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', padding: '10vh 0', color: 'var(--muted)' }}>
    ...
  </div>
)

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        {/* English site at "/" */}
        <Route path="/" element={<Layout lang="en" />}>
          <Route index element={<Home />} />
          <Route path="pricing" element={<Pricing />} />
          <Route path="about" element={<About />} />
          <Route path="contact" element={<Contact />} />
          <Route path="support" element={<Support />} />
          <Route path="privacy" element={<Privacy />} />
          <Route path="refund" element={<Refund />} />
          <Route path="get-started" element={<GetStarted />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Arabic site at "/ar" */}
        <Route path="/ar" element={<Layout lang="ar" />}>
          <Route index element={<Home />} />
          <Route path="pricing" element={<Pricing />} />
          <Route path="about" element={<About />} />
          <Route path="contact" element={<Contact />} />
          <Route path="support" element={<Support />} />
          <Route path="privacy" element={<Privacy />} />
          <Route path="refund" element={<Refund />} />
          <Route path="get-started" element={<GetStarted />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
