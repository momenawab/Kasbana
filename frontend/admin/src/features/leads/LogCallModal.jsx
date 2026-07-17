import { useState } from 'react'
import { Loader2, PhoneCall, X } from 'lucide-react'
import { useLogCall } from './api'
import { KIND, optionsFor } from './crm'
import { normalizeError } from '../../lib/api'

// Log Call.
//
// Call results are their own fixed vocabulary (CallResult on the backend), not
// the lead's status list: a call's outcome and a lead's state are different
// things, and a call cannot result in "Converted". They are not configurable in
// Settings for the same reason.
const RESULTS = [
  { slug: 'answered', label: 'Answered' },
  { slug: 'no_answer', label: 'No Answer' },
  { slug: 'busy', label: 'Busy' },
  { slug: 'phone_off', label: 'Phone Off' },
  { slug: 'wrong_number', label: 'Wrong Number' },
  { slug: 'reception_answered', label: 'Reception Answered' },
  { slug: 'manager_answered', label: 'Manager Answered' },
  { slug: 'owner_answered', label: 'Owner Answered' },
  { slug: 'call_back_later', label: 'Call Back Later' },
  { slug: 'not_interested', label: 'Not Interested' },
]

// Datetime-local wants `YYYY-MM-DDTHH:mm` in *local* time — toISOString would
// hand it UTC and silently shift the default by the timezone offset.
function localNow() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

export default function LogCallModal({ leadId, onClose, choices }) {
  const [form, setForm] = useState({
    called_at: localNow(),
    duration_minutes: '',
    result: 'answered',
    contact_method: 'phone',
    next_follow_up_at: '',
    notes: '',
  })
  const [err, setErr] = useState('')
  const log = useLogCall()

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setErr('')
    try {
      await log.mutateAsync({
        leadId,
        called_at: new Date(form.called_at).toISOString(),
        // The form asks for minutes because that is how people think about a
        // call; the API stores seconds because that is what it is.
        duration_seconds: Math.round((Number(form.duration_minutes) || 0) * 60),
        result: form.result,
        contact_method: form.contact_method,
        next_follow_up_at: form.next_follow_up_at
          ? new Date(form.next_follow_up_at).toISOString()
          : null,
        notes: form.notes,
      })
      onClose()
    } catch (e2) {
      setErr(normalizeError(e2).message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="w-full max-w-md rounded-card border border-line bg-surface p-5"
      >
        <div className="mb-4 flex items-start justify-between">
          <div className="flex items-center gap-2 text-tx">
            <PhoneCall size={17} className="text-brand" />
            <h2 className="font-head font-semibold">Log Call</h2>
          </div>
          <button type="button" onClick={onClose} className="text-tx-3 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Labelled label="Call date">
            <input
              type="datetime-local"
              value={form.called_at}
              onChange={set('called_at')}
              required
              className={inputClass}
            />
          </Labelled>
          <Labelled label="Duration (minutes)">
            <input
              type="number"
              min="0"
              step="1"
              value={form.duration_minutes}
              onChange={set('duration_minutes')}
              placeholder="0"
              className={inputClass}
            />
          </Labelled>
          <Labelled label="Result">
            <select value={form.result} onChange={set('result')} className={inputClass}>
              {RESULTS.map((r) => (
                <option key={r.slug} value={r.slug}>
                  {r.label}
                </option>
              ))}
            </select>
          </Labelled>
          <Labelled label="Contact method">
            <select
              value={form.contact_method}
              onChange={set('contact_method')}
              className={inputClass}
            >
              {optionsFor(choices, KIND.CONTACT_METHOD).map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.label}
                </option>
              ))}
            </select>
          </Labelled>
        </div>

        <Labelled label="Next follow-up" className="mt-3">
          <input
            type="datetime-local"
            value={form.next_follow_up_at}
            onChange={set('next_follow_up_at')}
            className={inputClass}
          />
        </Labelled>

        <Labelled label="Notes" className="mt-3">
          <textarea
            value={form.notes}
            onChange={set('notes')}
            rows={3}
            placeholder="What was said?"
            className={inputClass}
          />
        </Labelled>

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
            disabled={log.isPending}
            className="flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-d disabled:opacity-50"
          >
            {log.isPending && <Loader2 size={14} className="animate-spin" />}
            Save
          </button>
        </div>
      </form>
    </div>
  )
}

const inputClass =
  'w-full rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx placeholder:text-tx-3 focus:border-brand focus:outline-none'

function Labelled({ label, className = '', children }) {
  return (
    <label className={`flex flex-col gap-1 text-xs text-tx-3 ${className}`}>
      {label}
      {children}
    </label>
  )
}
