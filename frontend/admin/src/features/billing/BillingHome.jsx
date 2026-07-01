import { useState } from 'react'
import InvoicesTab from './InvoicesTab'
import DunningTab from './DunningTab'
import ReconciliationTab from './ReconciliationTab'

const TABS = [
  { key: 'invoices', label: 'Invoices' },
  { key: 'dunning', label: 'Dunning' },
  { key: 'reconciliation', label: 'Reconciliation' },
]

export default function BillingHome() {
  const [tab, setTab] = useState('invoices')

  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Billing</h1>

      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={
              'relative px-3 py-2 text-sm ' +
              (tab === t.key ? 'text-brand' : 'text-tx-3 hover:text-tx-2')
            }
          >
            {t.label}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-brand" />}
          </button>
        ))}
      </div>

      {tab === 'invoices' && <InvoicesTab />}
      {tab === 'dunning' && <DunningTab />}
      {tab === 'reconciliation' && <ReconciliationTab />}
    </div>
  )
}
