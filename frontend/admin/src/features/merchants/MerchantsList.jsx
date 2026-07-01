import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2, Building2 } from 'lucide-react'
import { useMerchants } from './api'
import Badge from '../../components/Badge'
import { num, shortDate, statusTone } from '../../lib/format'

const STATUS = ['', 'ACTIVE', 'SUSPENDED']
const PLAN = ['', 'trial', 'starter', 'growth', 'chain']

export default function MerchantsList() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [plan, setPlan] = useState('')
  const { data, isLoading, isFetching } = useMerchants({ q, status, plan })
  const rows = data?.results ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">Merchants</h1>
        {isFetching && <Loader2 size={16} className="animate-spin text-tx-3" />}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-1 items-center gap-2 rounded-ctl border border-line bg-surface px-3 py-2">
          <Search size={16} className="text-tx-3" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, slug…"
            className="flex-1 bg-transparent text-sm text-tx outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-ctl border border-line bg-surface px-3 py-2 text-sm text-tx"
        >
          {STATUS.map((s) => (
            <option key={s} value={s}>
              {s || 'All statuses'}
            </option>
          ))}
        </select>
        <select
          value={plan}
          onChange={(e) => setPlan(e.target.value)}
          className="rounded-ctl border border-line bg-surface px-3 py-2 text-sm text-tx"
        >
          {PLAN.map((p) => (
            <option key={p} value={p}>
              {p ? p[0].toUpperCase() + p.slice(1) : 'All plans'}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Merchant</th>
              <th className="px-4 py-3 font-medium">Plan</th>
              <th className="px-4 py-3 font-medium">Billing</th>
              <th className="px-4 py-3 font-medium text-right">Customers</th>
              <th className="px-4 py-3 font-medium text-right">Cards</th>
              <th className="px-4 py-3 font-medium text-right">Staff</th>
              <th className="px-4 py-3 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-tx-3">
                  <Loader2 size={18} className="mx-auto animate-spin" />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-tx-3">
                  <Building2 size={22} className="mx-auto mb-2" />
                  No merchants match.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => navigate(`/merchants/${r.id}`)}
                  className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-surface-2"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-tx">{r.name}</div>
                    <div className="text-xs text-tx-3">{r.slug}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="brand">{r.plan}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(r.billing_status)}>{r.billing_status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-num">{num(r.customers_count)}</td>
                  <td className="px-4 py-3 text-right font-num">{num(r.cards_count)}</td>
                  <td className="px-4 py-3 text-right font-num">{num(r.staff_count)}</td>
                  <td className="px-4 py-3 text-tx-2">{shortDate(r.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
