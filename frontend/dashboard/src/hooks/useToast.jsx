// Minimal toast system: useToast() -> {success,error,info}.
/* eslint-disable react-refresh/only-export-components -- provider + hook colocated by design */
import { createContext, useCallback, useContext, useState } from 'react'

const ToastContext = createContext(null)

let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const push = useCallback((tone, message) => {
    const id = nextId++
    setToasts((t) => [...t, { id, tone, message }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])

  const api = {
    success: (m) => push('success', m),
    error: (m) => push('danger', m),
    info: (m) => push('info', m),
  }

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed bottom-4 end-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={
              'rounded-ctl px-4 py-2 text-sm text-white shadow-bold ' +
              (t.tone === 'danger' ? 'bg-danger' : t.tone === 'success' ? 'bg-success' : 'bg-slate')
            }
            role="status"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
