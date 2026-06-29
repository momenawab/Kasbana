import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import App from './App'
import i18n from './lib/i18n'
import { queryClient } from './lib/queryClient'
import { bootstrapSession } from './lib/api'
import { ToastProvider } from './hooks/useToast'
import './index.css'

async function enableMocking() {
  if (import.meta.env.VITE_USE_MOCKS !== '1') return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })
}

async function start() {
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
