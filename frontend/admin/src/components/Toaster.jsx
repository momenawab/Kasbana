// Renders the toasts emitted through hooks/useToast. Mount once inside any
// screen that raises them.
import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'
import { subscribe } from '../hooks/useToast'

export default function Toaster() {
  const [items, setItems] = useState([])

  useEffect(
    () =>
      subscribe((toast) => {
        setItems((prev) => [...prev, toast])
        // Errors linger — an admin who looked away should still be able to read
        // why a save failed.
        const ttl = toast.tone === 'error' ? 8000 : 3500
        setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== toast.id)), ttl)
      }),
    []
  )

  if (!items.length) return null
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {items.map((toast) => {
        const bad = toast.tone === 'error'
        const Icon = bad ? XCircle : CheckCircle2
        return (
          <div
            key={toast.id}
            role="status"
            className={`pointer-events-auto flex max-w-sm items-start gap-2 rounded-ctl border px-3 py-2 text-sm shadow-card ${
              bad ? 'border-danger/40 bg-surface' : 'border-success/40 bg-surface'
            }`}
          >
            <Icon size={16} className={`mt-0.5 shrink-0 ${bad ? 'text-danger' : 'text-success'}`} />
            <span className="text-tx">{toast.message}</span>
          </div>
        )
      })}
    </div>
  )
}
