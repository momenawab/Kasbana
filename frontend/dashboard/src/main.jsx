import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import App from './App'
import i18n from './lib/i18n'
import { queryClient } from './lib/queryClient'
import { bootstrapSession } from './lib/api'
import { startImpersonation } from './lib/auth'
import { ToastProvider } from './hooks/useToast'
import './index.css'

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
              <App />
            </BrowserRouter>
          </ToastProvider>
        </QueryClientProvider>
      </I18nextProvider>
    </React.StrictMode>
  )
}

start()
