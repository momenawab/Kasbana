import { useEffect, useState } from 'react'
import { Loader2, Save, ShieldCheck } from 'lucide-react'
import { useRetention, useUpdateRetention } from './api'
import { useAuth } from '../../hooks/useAuth'
import { normalizeError } from '../../lib/api'

const FIELDS = [
  {
    key: 'inactive_customer_days',
    label: 'Inactive customer cards',
    hint: 'Days of no activity before a card is eligible for purge.',
  },
  {
    key: 'closed_merchant_days',
    label: 'Closed merchant data',
    hint: 'Days to retain data of churned/closed merchants.',
  },
  { key: 'audit_log_days', label: 'Audit log', hint: 'Days to retain the admin audit trail.' },
]

export default function ComplianceHome() {
  const { role } = useAuth()
  const canEdit = role === 'SUPER_ADMIN'
  const { data, isLoading } = useRetention()
  const update = useUpdateRetention()
  const [form, setForm] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data && form === null) {
      setForm({
        inactive_customer_days: data.inactive_customer_days,
        closed_merchant_days: data.closed_merchant_days,
        audit_log_days: data.audit_log_days,
        notes: data.notes || '',
      })
    }
  }, [data, form])

  if (isLoading || !form) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  const setNum = (k) => (e) => setForm((f) => ({ ...f, [k]: Number(e.target.value) }))

  async function save(e) {
    e.preventDefault()
    setSaved(false)
    try {
      await update.mutateAsync(form)
      setSaved(true)
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-tx">Compliance — Data Retention</h1>
      <p className="text-sm text-tx-3">
        The platform-wide data-retention policy (PDPL). A window of <strong>0</strong> means keep
        indefinitely. Setting a window records the intent and is audited; automated purging lands in
        a later phase. Per-merchant export and erasure live on each merchant’s Compliance tab.
      </p>

      <form
        onSubmit={save}
        className="flex flex-col gap-4 rounded-card border border-line bg-surface p-5"
      >
        {FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col gap-1">
            <span className="text-sm font-medium text-tx">{f.label}</span>
            <span className="text-xs text-tx-3">{f.hint}</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                type="number"
                min={0}
                disabled={!canEdit}
                value={form[f.key]}
                onChange={setNum(f.key)}
                className="w-32 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none disabled:opacity-60"
              />
              <span className="text-sm text-tx-3">days</span>
            </div>
          </label>
        ))}

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-tx">Notes</span>
          <textarea
            rows={3}
            disabled={!canEdit}
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            className="rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none disabled:opacity-60"
          />
        </label>

        {data.updated_by_email && (
          <div className="text-xs text-tx-3">
            Last updated by {data.updated_by_email} · {new Date(data.updated_at).toLocaleString()}
          </div>
        )}

        {canEdit ? (
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={update.isPending}
              className="flex items-center gap-1.5 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-bg disabled:opacity-60"
            >
              <Save size={15} /> Save policy
            </button>
            {saved && (
              <span className="flex items-center gap-1 text-sm text-success">
                <ShieldCheck size={15} /> Saved
              </span>
            )}
          </div>
        ) : (
          <p className="text-sm text-tx-3">Only super-admins can edit the retention policy.</p>
        )}
      </form>
    </div>
  )
}
