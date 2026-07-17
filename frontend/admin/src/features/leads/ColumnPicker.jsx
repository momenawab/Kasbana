import { useEffect, useRef, useState } from 'react'
import { Columns3 } from 'lucide-react'
import { COLUMNS } from './columns'

// Column visibility. Persisted to localStorage because which columns matter is
// a property of the person, not the session — someone who works by follow-up
// date should not re-pick their columns every morning.
export default function ColumnPicker({ visible, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const away = (e) => !ref.current?.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open])

  const toggle = (key) =>
    onChange(visible.includes(key) ? visible.filter((k) => k !== key) : [...visible, key])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 rounded-ctl border px-3 py-2 text-sm transition ${
          open ? 'border-brand text-brand' : 'border-line text-tx-2 hover:border-brand hover:text-brand'
        }`}
      >
        <Columns3 size={15} />
        Columns
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-52 rounded-card border border-line bg-surface p-2 shadow-pop">
          {COLUMNS.map((c) => (
            <label
              key={c.key}
              className={`flex items-center gap-2 rounded-ctl px-2 py-1.5 text-sm ${
                c.always ? 'text-tx-3' : 'cursor-pointer text-tx-2 hover:bg-surface-2'
              }`}
            >
              <input
                type="checkbox"
                checked={visible.includes(c.key)}
                // The identifying column cannot be hidden: a table of leads with
                // no business name is a table of nothing.
                disabled={c.always}
                onChange={() => toggle(c.key)}
                className="accent-brand"
              />
              {c.label}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
