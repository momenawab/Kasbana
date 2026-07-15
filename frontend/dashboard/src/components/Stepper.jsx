import { Check } from 'lucide-react'

// Stepper (spec §10) — {steps:[label], current} (0-based). Used by Onboarding.
export default function Stepper({ steps, current }) {
  return (
    <ol className="flex items-center gap-2">
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                done
                  ? 'bg-teal text-white'
                  : active
                    ? 'bg-violet text-white'
                    : 'bg-paper text-tx-3 border border-line'
              }`}
            >
              {done ? <Check size={14} /> : i + 1}
            </span>
            <span className={`text-sm ${active ? 'text-tx font-medium' : 'text-tx-2'}`}>
              {label}
            </span>
            {i < steps.length - 1 && <span className="h-px flex-1 bg-line" />}
          </li>
        )
      })}
    </ol>
  )
}
