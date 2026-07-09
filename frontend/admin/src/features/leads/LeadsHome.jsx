import { Loader2, Mail, Phone, Trash2, Check, RotateCcw } from 'lucide-react'
import { useLeads, useUpdateLead, useDeleteLead } from './api'
import Badge from '../../components/Badge'
import { fromNow } from '../../lib/format'

const STATUS_TONE = { new: 'info', contacted: 'success' }
const STATUS_LABEL = { new: 'New', contacted: 'Contacted' }

export default function LeadsHome() {
  const { data, isLoading } = useLeads()
  const rows = data ?? []
  const newCount = rows.filter((r) => r.status === 'new').length

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <h1 className="font-head text-2xl font-bold text-tx">Leads</h1>
        {newCount > 0 && <Badge tone="info">{newCount} new</Badge>}
      </div>
      <p className="-mt-3 text-sm text-tx-3">
        Inbound “Get started” requests from the marketing site.
      </p>

      {isLoading ? (
        <Loader2 className="mx-auto mt-6 animate-spin text-tx-3" />
      ) : (
        <List rows={rows} />
      )}
    </div>
  )
}

function List({ rows }) {
  const update = useUpdateLead()
  const del = useDeleteLead()

  if (rows.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3">
        No leads yet.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-tx-3">
            <th className="px-4 py-3 font-semibold">Business</th>
            <th className="px-4 py-3 font-semibold">Contact</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Received</th>
            <th className="px-4 py-3 font-semibold text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((lead) => (
            <tr key={lead.id} className="border-b border-line last:border-0">
              <td className="px-4 py-3">
                <div className="font-semibold text-tx">{lead.business_name}</div>
              </td>
              <td className="px-4 py-3">
                <div className="text-tx">{lead.name}</div>
                <div className="mt-1 flex flex-col gap-0.5 text-xs text-tx-3">
                  <a
                    href={`mailto:${lead.email}`}
                    className="flex items-center gap-1 hover:text-brand"
                  >
                    <Mail size={12} /> {lead.email}
                  </a>
                  <a
                    href={`tel:${lead.phone}`}
                    className="flex items-center gap-1 hover:text-brand"
                  >
                    <Phone size={12} /> {lead.phone}
                  </a>
                </div>
              </td>
              <td className="px-4 py-3">
                <Badge tone={STATUS_TONE[lead.status]}>
                  {STATUS_LABEL[lead.status] ?? lead.status}
                </Badge>
              </td>
              <td className="px-4 py-3 text-tx-3">{fromNow(lead.created_at)}</td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  {lead.status === 'new' ? (
                    <button
                      onClick={() => update.mutate({ id: lead.id, status: 'contacted' })}
                      disabled={update.isPending}
                      className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-success hover:text-success disabled:opacity-60"
                    >
                      <Check size={14} /> Mark contacted
                    </button>
                  ) : (
                    <button
                      onClick={() => update.mutate({ id: lead.id, status: 'new' })}
                      disabled={update.isPending}
                      className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
                    >
                      <RotateCcw size={14} /> Reopen
                    </button>
                  )}
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete lead from ${lead.business_name}?`)) {
                        del.mutate(lead.id)
                      }
                    }}
                    disabled={del.isPending}
                    className="flex items-center gap-1 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-danger hover:text-danger disabled:opacity-60"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
