import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2 } from 'lucide-react'
import { useReconciliation } from './api'
import Badge from '../../components/Badge'
import { num, shortDate } from '../../lib/format'

export default function ReconciliationTab() {
  const navigate = useNavigate()
  const { data, isLoading } = useReconciliation()

  if (isLoading || !data) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  const { stale_pending_invoices: stalePending, active_without_paid_invoice: activeGap } = data
  const clean = stalePending.length === 0 && activeGap.length === 0

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-tx-3">
        Internal consistency checks against our own records — not a live Paymob
        transaction-log match (needs real gateway credentials).
      </p>

      {clean && (
        <div className="flex items-center gap-2 rounded-card border border-line bg-surface p-5 text-sm text-tx-2">
          <CheckCircle2 size={18} className="text-success" />
          No issues found.
        </div>
      )}

      {stalePending.length > 0 && (
        <div>
          <h2 className="mb-2 font-head text-sm font-semibold text-tx">
            Stale pending invoices (7+ days, no payment recorded)
          </h2>
          <div className="overflow-hidden rounded-card border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-tx-3">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium">Merchant</th>
                  <th className="px-4 py-3 font-medium text-right">Amount</th>
                  <th className="px-4 py-3 font-medium">Issued</th>
                  <th className="px-4 py-3 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {stalePending.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => navigate(`/merchants/${row.merchant.id}`)}
                    className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2"
                  >
                    <td className="px-4 py-3 text-tx">{row.merchant.name}</td>
                    <td className="px-4 py-3 text-right font-num">{num(row.amount_egp)} EGP</td>
                    <td className="px-4 py-3 text-tx-2">{shortDate(row.issued_at)}</td>
                    <td className="px-4 py-3 text-tx-2">{row.note || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeGap.length > 0 && (
        <div>
          <h2 className="mb-2 font-head text-sm font-semibold text-tx">
            Active via a gateway checkout, but no paid invoice on record
          </h2>
          <div className="overflow-hidden rounded-card border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-tx-3">
                <tr className="text-left">
                  <th className="px-4 py-3 font-medium">Merchant</th>
                  <th className="px-4 py-3 font-medium">Plan</th>
                  <th className="px-4 py-3 font-medium">Provider</th>
                </tr>
              </thead>
              <tbody>
                {activeGap.map((row) => (
                  <tr
                    key={row.merchant.id}
                    onClick={() => navigate(`/merchants/${row.merchant.id}`)}
                    className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2"
                  >
                    <td className="px-4 py-3 text-tx">{row.merchant.name}</td>
                    <td className="px-4 py-3">
                      <Badge tone="brand">{row.plan}</Badge>
                    </td>
                    <td className="px-4 py-3 text-tx-2">{row.provider}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
