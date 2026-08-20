import { useState } from 'react'
import { Loader2, Receipt } from 'lucide-react'
import { useInvoices, useInvoice, useRetryInvoice } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { normalizeError } from '../../lib/api'
import { num, shortDate, statusTone } from '../../lib/format'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']
const STATUSES = ['', 'paid', 'pending', 'failed']

export default function InvoicesTab() {
  const { role } = useAuth()
  const canRetry = FINANCE_ROLES.includes(role)
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState(null)
  const { data, isLoading, isFetching } = useInvoices(status ? { status } : {})
  const rows = data?.results ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-ctl border border-line bg-surface px-3 py-2 text-sm text-tx"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s ? s[0].toUpperCase() + s.slice(1) : 'All statuses'}
            </option>
          ))}
        </select>
        {isFetching && <Loader2 size={16} className="animate-spin text-tx-3" />}
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Merchant</th>
              <th className="px-4 py-3 font-medium text-right">Amount</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Provider</th>
              <th className="px-4 py-3 font-medium">Issued</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-tx-3">
                  <Loader2 size={18} className="mx-auto animate-spin" />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-tx-3">
                  <Receipt size={22} className="mx-auto mb-2" />
                  No invoices match.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => setSelected(r.id)}
                  className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-tx">{r.merchant.name}</div>
                    <div className="text-xs text-tx-3">{r.merchant.slug}</div>
                  </td>
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

      {selected && (
        <InvoiceDetail id={selected} canRetry={canRetry} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function InvoiceDetail({ id, canRetry, onClose }) {
  const { data: invoice, isLoading } = useInvoice(id)
  const retry = useRetryInvoice()
  const [error, setError] = useState('')

  async function runRetry() {
    if (!window.confirm('Retry this failed charge? A new checkout will be created.')) return
    setError('')
    try {
      const { checkout_url } = await retry.mutateAsync(id)
      window.alert(`New checkout created:\n${checkout_url}`)
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  if (isLoading || !invoice) {
    return <Loader2 className="mx-auto mt-4 animate-spin text-tx-3" />
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-head text-lg font-semibold text-tx">
          {invoice.merchant.name} — {num(invoice.amount_egp)} EGP
        </h2>
        <button onClick={onClose} className="text-sm text-tx-3 hover:text-tx">
          Close
        </button>
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <Row label="Status" value={<Badge tone={statusTone(invoice.status)}>{invoice.status}</Badge>} />
        <Row label="Provider" value={invoice.provider || 'manual'} />
        <Row label="Gateway ref" value={invoice.gateway_ref || '—'} />
        <Row label="Issued" value={shortDate(invoice.issued_at)} />
        {invoice.note && <Row label="Note" value={invoice.note} />}
      </dl>
      {error && <p className="text-sm text-danger">{error}</p>}
      {canRetry && invoice.status === 'failed' && (
        <button
          onClick={runRetry}
          disabled={retry.isPending}
          className="w-fit rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-60"
        >
          Retry charge
        </button>
      )}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-tx-3">{label}</dt>
      <dd className="text-right text-tx">{value}</dd>
    </div>
  )
}
