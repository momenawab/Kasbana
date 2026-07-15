import { useState } from 'react'
import { Loader2, CreditCard, Plus, Archive, ArchiveRestore } from 'lucide-react'
import { usePlans, useSavePlan } from './api'
import { useAuth } from '../../hooks/useAuth'
import Badge from '../../components/Badge'
import { num } from '../../lib/format'
import PlanForm from './PlanForm'

const FINANCE_ROLES = ['SUPER_ADMIN', 'FINANCE']

function limitLabel(v) {
  return v == null ? 'Unlimited' : num(v)
}

export default function PlansList() {
  const { role } = useAuth()
  const canEdit = FINANCE_ROLES.includes(role)
  const [showArchived, setShowArchived] = useState(false)
  const [editing, setEditing] = useState(null) // null | 'new' | plan object
  const { data: plans = [], isLoading, isFetching } = usePlans(showArchived)
  const archiveToggle = useSavePlan()

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">Plans</h1>
        {isFetching && <Loader2 size={16} className="animate-spin text-tx-3" />}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-sm text-tx-2">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          Show archived
        </label>
        {canEdit && editing == null && (
          <button
            onClick={() => setEditing('new')}
            className="inline-flex items-center gap-2 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-white hover:bg-brand-d"
          >
            <Plus size={16} /> New plan
          </button>
        )}
      </div>

      {editing != null && (
        <PlanForm
          plan={editing === 'new' ? null : editing}
          onDone={() => setEditing(null)}
          onCancel={() => setEditing(null)}
        />
      )}

      <div className="overflow-hidden rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Plan</th>
              <th className="px-4 py-3 font-medium">Price</th>
              <th className="px-4 py-3 font-medium text-right">Cards</th>
              <th className="px-4 py-3 font-medium text-right">Locations</th>
              <th className="px-4 py-3 font-medium text-right">Staff</th>
              <th className="px-4 py-3 font-medium text-right">Customers</th>
              <th className="px-4 py-3 font-medium">Status</th>
              {canEdit && <th className="px-4 py-3 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-tx-3">
                  <Loader2 size={18} className="mx-auto animate-spin" />
                </td>
              </tr>
            ) : plans.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-tx-3">
                  <CreditCard size={22} className="mx-auto mb-2" />
                  No plans yet.
                </td>
              </tr>
            ) : (
              plans.map((p) => (
                <tr
                  key={p.key}
                  className="border-b border-line/60 last:border-0 hover:bg-surface-2"
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-tx">{p.name}</div>
                    <div className="text-xs text-tx-3">{p.key}</div>
                  </td>
                  <td className="px-4 py-3 font-num">{num(p.price_egp)} EGP</td>
                  <td className="px-4 py-3 text-right font-num">{limitLabel(p.max_cards)}</td>
                  <td className="px-4 py-3 text-right font-num">{limitLabel(p.max_locations)}</td>
                  <td className="px-4 py-3 text-right font-num">{limitLabel(p.max_staff)}</td>
                  <td className="px-4 py-3 text-right font-num">{limitLabel(p.max_customers)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {p.archived && <Badge tone="danger">Archived</Badge>}
                      <Badge tone={p.is_public ? 'success' : 'neutral'}>
                        {p.is_public ? 'Public' : 'Private'}
                      </Badge>
                    </div>
                  </td>
                  {canEdit && (
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setEditing(p)}
                          className="text-xs font-semibold text-brand hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            archiveToggle.mutate({ key: p.key, archived: !p.archived })
                          }
                          title={p.archived ? 'Unarchive' : 'Archive'}
                          className="text-tx-3 hover:text-tx"
                        >
                          {p.archived ? <ArchiveRestore size={16} /> : <Archive size={16} />}
                        </button>
                      </div>
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
