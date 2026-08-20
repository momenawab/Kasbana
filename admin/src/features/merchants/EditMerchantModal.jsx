import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { useUpdateMerchant } from './api'
import { normalizeError } from '../../lib/api'

// Edit a merchant's core profile. Only fields that actually changed are sent,
// so a no-op save is a no-op on the server (and audits nothing).
export default function EditMerchantModal({ merchant, onClose }) {
  const [form, setForm] = useState({
    name: merchant.name || '',
    legal_name: merchant.legal_name || '',
    contact_email: merchant.contact?.email || '',
    contact_phone: merchant.contact?.name || '', // phone is carried in contact.name
  })
  const [err, setErr] = useState('')
  const update = useUpdateMerchant(merchant.id)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const canSubmit = form.name.trim() && !update.isPending

  const initial = {
    name: merchant.name || '',
    legal_name: merchant.legal_name || '',
    contact_email: merchant.contact?.email || '',
    contact_phone: merchant.contact?.name || '',
  }

  async function submit(e) {
    e.preventDefault()
    setErr('')
    // Diff against the loaded values — send only what changed.
    const body = Object.fromEntries(
      Object.entries(form).filter(([k, v]) => v.trim() !== (initial[k] || '').trim())
    )
    if (Object.keys(body).length === 0) {
      onClose()
      return
    }
    try {
      await update.mutateAsync(body)
      onClose()
    } catch (e2) {
      setErr(normalizeError(e2).message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <form
        onSubmit={submit}
        className="my-8 w-full max-w-lg rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-head text-lg font-semibold text-tx">Edit merchant</h2>
            <p className="mt-0.5 text-xs text-tx-3">Changes are audited.</p>
          </div>
          <button type="button" onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Business name" required value={form.name} onChange={set('name')} />
          <Field label="Legal name" value={form.legal_name} onChange={set('legal_name')} />
          <Field
            label="Contact email"
            type="email"
            value={form.contact_email}
            onChange={set('contact_email')}
          />
          <Field label="Contact phone" value={form.contact_phone} onChange={set('contact_phone')} />
        </div>

        {err && <div className="mt-3 text-sm text-danger">{err}</div>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
          >
            {update.isPending && <Loader2 size={14} className="animate-spin" />}
            Save changes
          </button>
        </div>
      </form>
    </div>
  )
}

const inputClass =
  'rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none'

function Field({ label, required, ...props }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      <span>
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </span>
      <input {...props} required={required} className={inputClass} />
    </label>
  )
}
