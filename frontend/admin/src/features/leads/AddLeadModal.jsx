import { useState } from 'react'
import { AlertTriangle, Loader2, X } from 'lucide-react'
import { useCreateLead, useDuplicateCheck, useSalesUsers } from './api'
import { KIND, optionsFor } from './crm'
import { normalizeError } from '../../lib/api'
import { useDebounced } from './useDebounced'

// Add Lead. Type and creator are not on this form on purpose — the backend
// stamps them from the fact that a logged-in user posted it, and offering them
// would invite a manual lead that claims to be a website one.
//
// Duplicate detection runs twice, and both are needed: this form warns while
// the user types (cheap, advisory, dismissible), and the POST re-checks
// server-side (authoritative, race-free). A warning here is a courtesy; the 409
// is the actual guard.
export default function AddLeadModal({ onClose, onCreated, choices }) {
  const [form, setForm] = useState({
    business_name: '',
    name: '',
    phone: '',
    whatsapp: '',
    email: '',
    area: '',
    category: '',
    source: 'manual',
    status: 'new_lead',
    priority: 'medium',
    temperature: 'warm',
    assigned_sales: '',
    notes: '',
  })
  const [err, setErr] = useState('')
  const [dupes, setDupes] = useState(null) // set when the server says 409

  const create = useCreateLead()
  const { data: salesUsers } = useSalesUsers()

  // Debounced so typing a phone number is not eleven requests.
  const probe = useDebounced({ phone: form.phone, business_name: form.business_name }, 400)
  const { data: liveDupes } = useDuplicateCheck(probe)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const canSubmit = form.business_name.trim() && form.phone.trim() && !create.isPending

  async function submit(e, { force = false } = {}) {
    e?.preventDefault()
    setErr('')
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ''))
      const lead = await create.mutateAsync({ ...body, force })
      onCreated?.(lead)
      onClose()
    } catch (e2) {
      const data = e2.response?.data?.error
      if (e2.response?.status === 409 && data?.code === 'POSSIBLE_DUPLICATE') {
        setDupes(data.duplicates ?? [])
        return
      }
      // The envelope's top-level message for a 400 is always "Validation
      // failed." — useless on its own. The `fields` map is where the actual
      // reason is, so spell it out rather than making the user guess.
      const { message, fields } = normalizeError(e2)
      const detail = Object.entries(fields)
        .map(([f, msgs]) => `${f.replace(/_/g, ' ')}: ${[].concat(msgs).join(' ')}`)
        .join(' · ')
      setErr(detail || message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <form
        onSubmit={submit}
        className="my-8 w-full max-w-2xl rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="font-head text-lg font-semibold text-tx">Add Lead</h2>
            <p className="mt-0.5 text-xs text-tx-3">
              Created as a manual lead under your name.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        {dupes ? (
          <DuplicateWarning
            duplicates={dupes}
            onOpen={onClose}
            onBack={() => setDupes(null)}
            onForce={(e) => submit(e, { force: true })}
            busy={create.isPending}
          />
        ) : (
          <>
            {liveDupes?.length > 0 && (
              <div className="mb-4 flex items-start gap-2 rounded-ctl border border-warn/40 bg-warn/10 p-3 text-xs text-warn">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <span>
                  {liveDupes.length === 1
                    ? `${liveDupes[0].business_name} already has a lead with this phone or name.`
                    : `${liveDupes.length} existing leads match this phone or name.`}
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Business name" required value={form.business_name} onChange={set('business_name')} />
              <Field label="Owner" value={form.name} onChange={set('name')} />
              <Field label="Phone" required value={form.phone} onChange={set('phone')} />
              <Field label="WhatsApp" value={form.whatsapp} onChange={set('whatsapp')} />
              <Field label="Email" type="email" value={form.email} onChange={set('email')} />
              <Field label="Area" value={form.area} onChange={set('area')} />

              <Picker label="Category" value={form.category} onChange={set('category')} blank="—">
                {optionsFor(choices, KIND.CATEGORY).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                ))}
              </Picker>
              <Picker label="Source" value={form.source} onChange={set('source')}>
                {optionsFor(choices, KIND.SOURCE).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                ))}
              </Picker>
              <Picker label="Status" value={form.status} onChange={set('status')}>
                {optionsFor(choices, KIND.STATUS).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                ))}
              </Picker>
              <Picker label="Priority" value={form.priority} onChange={set('priority')}>
                {optionsFor(choices, KIND.PRIORITY).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                ))}
              </Picker>
              <Picker label="Temperature" value={form.temperature} onChange={set('temperature')}>
                {optionsFor(choices, KIND.TEMPERATURE).map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.label}
                  </option>
                ))}
              </Picker>
              <Picker
                label="Assigned sales"
                value={form.assigned_sales}
                onChange={set('assigned_sales')}
                blank="Unassigned"
              >
                {(salesUsers ?? []).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name || a.email}
                  </option>
                ))}
              </Picker>
            </div>

            <label className="mt-3 flex flex-col gap-1 text-xs text-tx-3">
              Notes
              <textarea
                value={form.notes}
                onChange={set('notes')}
                rows={3}
                className="rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
              />
            </label>

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
                {create.isPending && <Loader2 size={14} className="animate-spin" />}
                Add Lead
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}

// The three ways out of a duplicate, exactly as the spec asks: open the one that
// exists, go back and edit, or say "these really are different" and proceed.
// Merge is not here — it belongs on the details page, where there is something
// to merge into and a timeline to record it on.
function DuplicateWarning({ duplicates, onOpen, onBack, onForce, busy }) {
  return (
    <div>
      <div className="mb-3 flex items-start gap-2 rounded-ctl border border-warn/40 bg-warn/10 p-3 text-sm text-warn">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        <div>
          <div className="font-semibold">This lead may already exist</div>
          <div className="mt-0.5 text-xs opacity-90">
            Matching on phone, email or business name.
          </div>
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {duplicates.map((d) => (
          <li
            key={d.id}
            className="flex items-center justify-between rounded-ctl border border-line bg-bg px-3 py-2"
          >
            <div>
              <div className="text-sm font-medium text-tx">{d.business_name}</div>
              <div className="font-num text-xs text-tx-3">
                {d.phone} · {d.assigned_sales?.name || d.assigned_sales?.email || 'Unassigned'}
              </div>
            </div>
            <a
              href={`/leads/${d.id}`}
              onClick={onOpen}
              className="rounded-ctl border border-line px-3 py-1.5 text-xs text-tx-2 hover:border-brand hover:text-brand"
            >
              Open
            </a>
          </li>
        ))}
      </ul>

      <div className="mt-5 flex justify-end gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:text-tx"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onForce}
          disabled={busy}
          className="flex items-center gap-2 rounded-ctl border border-warn px-4 py-2 text-sm font-semibold text-warn hover:bg-warn/10 disabled:opacity-50"
        >
          {busy && <Loader2 size={14} className="animate-spin" />}
          Create anyway
        </button>
      </div>
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

function Picker({ label, blank, children, ...props }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tx-3">
      {label}
      <select {...props} className={inputClass}>
        {blank && <option value="">{blank}</option>}
        {children}
      </select>
    </label>
  )
}
