import { useAuth } from '../../hooks/useAuth'

// Phase 1 landing — a welcome + a map of what each later phase unlocks. Real
// KPI tiles arrive with Platform Analytics (Phase 8).
const ROADMAP = [
  ['Merchants', 'Find & inspect every subscriber', 2],
  ['Plans', 'Edit plans, limits & pricing', 3],
  ['Subscriptions', 'Change plan, trial, comp, lock', 4],
  ['Billing', 'Invoices, refunds, dunning', 5],
  ['Support', 'Impersonate & fix accounts', 6],
  ['Revenue', 'MRR, churn, conversion', 7],
]

export default function Home() {
  const { admin } = useAuth()
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-head text-2xl font-bold text-tx">
          Welcome{admin?.name ? `, ${admin.name}` : ''}
        </h1>
        <p className="mt-1 text-sm text-tx-2">
          The platform admin console is live. Each area below unlocks as its phase ships.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ROADMAP.map(([title, desc, phase]) => (
          <div key={title} className="rounded-card border border-line bg-surface p-4">
            <div className="flex items-center justify-between">
              <span className="font-head font-semibold text-tx">{title}</span>
              <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-tx-3">
                Phase {phase}
              </span>
            </div>
            <p className="mt-1 text-sm text-tx-2">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
