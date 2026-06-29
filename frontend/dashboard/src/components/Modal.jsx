import { useEffect } from 'react'
import { X } from 'lucide-react'

// Modal + Drawer (spec §10). Drawer slides from the inline-end (RTL aware).
function useEscClose(open, onClose) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])
}

export function Modal({ open, onClose, title, children, footer }) {
  useEscClose(open, onClose)
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative w-full max-w-md rounded-card bg-white shadow-bold"
      >
        <header className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="font-head text-lg font-semibold text-ink">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-tx-3 hover:text-tx">
            <X size={20} />
          </button>
        </header>
        <div className="px-5 py-4">{children}</div>
        {footer && <footer className="border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>
  )
}

export function Drawer({ open, onClose, title, children, footer }) {
  useEscClose(open, onClose)
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="absolute inset-y-0 end-0 flex w-full max-w-md flex-col bg-white shadow-bold"
      >
        <header className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="font-head text-lg font-semibold text-ink">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-tx-3 hover:text-tx">
            <X size={20} />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>
  )
}
