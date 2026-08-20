import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, AlertTriangle } from 'lucide-react'
import { useDunning, useNotifyDunning } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, shortDate } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

export default function DunningTab() {
  const navigate = useNavigate()
  const { role } = useAuth()
  const canNotify = FINANCE_ROLES.includes(role)
  const { data: rows = [], isLoading } = useDunning()
  const notify = useNotifyDunning()
  const [error, setError] = useState('')
  const [notified, setNotified] = useState({})

  async function runNotify(merchantId) {
    if (!window.confirm('Send a payment-reminder email to this merchant’s owner?')) return
    setError('')
    try {
      await notify.mutateAsync({ merchantId, reason: '' })
      setNotified((n) => ({ ...n, [merchantId]: true }))
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  if (isLoading) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-danger">{error}</p>}
      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Merchant</th>
              <th className="px-4 py-3 font-medium">Plan</th>
              <th className="px-4 py-3 font-medium text-right">Last failed charge</th>
              <th className="px-4 py-3 font-medium">Failed on</th>
              {canNotify && <th className="px-4 py-3 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-tx-3">
                  <AlertTriangle size={22} className="mx-auto mb-2" />
                  No merchants past due.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.merchant.id} className="border-b border-line/60 last:border-0">
                  <td
                    className="cursor-pointer px-4 py-3 hover:underline"
                    onClick={() => navigate(`/merchants/${r.merchant.id}`)}
                  >
                    <div className="font-medium text-tx">{r.merchant.name}</div>
                    <div className="text-xs text-tx-3">{r.merchant.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="brand">{r.plan}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-num">
                    {r.last_failed_invoice ? `${num(r.last_failed_invoice.amount_egp)} EGP` : '—'}
                  </td>
                  <td className="px-4 py-3 text-tx-2">
                    {r.last_failed_invoice ? shortDate(r.last_failed_invoice.issued_at) : '—'}
                  </td>
                  {canNotify && (
                    <td className="px-4 py-3">
                      <button
                        onClick={() => runNotify(r.merchant.id)}
                        disabled={notify.isPending}
                        className="text-xs font-semibold text-brand hover:underline disabled:opacity-60"
                      >
                        {notified[r.merchant.id] ? 'Sent ✓' : 'Notify'}
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
