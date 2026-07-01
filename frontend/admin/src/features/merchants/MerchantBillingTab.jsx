import { useState } from 'react'
import { Loader2, Receipt } from 'lucide-react'
import { useInvoices, useCreateManualInvoice } from '../billing/api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, shortDate, statusTone } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

export default function MerchantBillingTab({ merchantId }) {
  const { role } = useAuth()
  const canRecord = FINANCE_ROLES.includes(role)
  const { data, isLoading } = useInvoices({ merchant_id: merchantId })
  const rows = data?.results ?? []

  const [form, setForm] = useState({ amount_egp: '', status: 'paid', note: '' })
  const [error, setError] = useState('')
  const create = useCreateManualInvoice(merchantId)

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await create.mutateAsync(form)
      setForm({ amount_egp: '', status: 'paid', note: '' })
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {canRecord && (
        <form
          onSubmit={submit}
          className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-4"
        >
          <label className="block">
            <span className="mb-1 block text-xs text-tx-3">Amount (EGP)</span>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={form.amount_egp}
              onChange={(e) => setForm({ ...form, amount_egp: e.target.value })}
              className="w-32 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-tx-3">Status</span>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
            >
              <option value="paid">Paid (offline payment received)</option>
              <option value="pending">Pending (expected, not yet received)</option>
            </select>
          </label>
          <label className="block flex-1">
            <span className="mb-1 block text-xs text-tx-3">Note</span>
            <input
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              placeholder="e.g. bank transfer ref #123"
              className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-tx outline-none focus:border-brand"
            />
          </label>
          <button
            type="submit"
            disabled={create.isPending || !form.amount_egp}
            className="rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg hover:bg-brand-d disabled:opacity-60"
          >
            Record invoice
          </button>
        </form>
      )}
      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium text-right">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Issued</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-tx-3">
                  <Loader2 size={18} className="mx-auto animate-spin" />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-tx-3">
                  <Receipt size={22} className="mx-auto mb-2" />
                  No invoices yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-b border-line/60 last:border-0">
                  <td className="px-4 py-3 text-right font-num">{num(r.amount_egp)} EGP</td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-tx-2">{r.provider || 'manual'}</td>
                  <td className="px-4 py-3 text-tx-2">{shortDate(r.issued_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
