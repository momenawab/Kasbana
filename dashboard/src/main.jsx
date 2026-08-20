import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import * as Sentry from '@sentry/react'
import App from './App'
import i18n from './lib/i18n'
import { queryClient } from './lib/queryClient'
import { bootstrapSession } from './lib/api'
import { startImpersonation } from './lib/auth'
import { ToastProvider } from './hooks/useToast'
import AppCrash from './components/AppCrash'
import './index.css'

// Merchant-dashboard browser error reporting (Phase 3). Mirrors the admin
// console (Phase 15): no-op unless VITE_SENTRY_DSN is set at build time, so dev
// and the mock build stay silent. Tagged so dashboard events are easy to
// separate from the admin console in Sentry. Query/mutation failures are
// captured in lib/queryClient; render + route errors via the ErrorBoundary below.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || 'production',
    release: import.meta.env.VITE_SENTRY_RELEASE || undefined,
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_RATE || 0.1),
    initialScope: { tags: { app: 'merchant-dashboard' } },
  })
}

// Admin "view as merchant" handoff (Phase 6): the admin console opens the
// dashboard with #impersonate=<short-lived token>. Capture it into
// sessionStorage before anything renders and scrub it from the URL/history.
function captureImpersonation() {
  const match = window.location.hash.match(/[#&]impersonate=([^&]+)/)
  if (!match) return
  startImpersonation(decodeURIComponent(match[1]))
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
}

async function enableMocking() {
  if (import.meta.env.VITE_USE_MOCKS !== '1') return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })
}

async function start() {
  captureImpersonation()
  await enableMocking()
  await bootstrapSession()

  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <ToastProvider>
            <BrowserRouter>
              <Sentry.ErrorBoundary fallback={<AppCrash />}>
                <App />
              </Sentry.ErrorBoundary>
            </BrowserRouter>
          </ToastProvider>
        </QueryClientProvider>
      </I18nextProvider>
    </React.StrictMode>
  )
}

start()
