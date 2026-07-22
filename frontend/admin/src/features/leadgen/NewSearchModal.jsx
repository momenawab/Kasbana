import { useState } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import { BUSINESS_TYPES, MAX_RESULTS, PRIORITIES } from './constants'
import { useCreateJob } from './api'
import { normalizeError } from '../../lib/api'

const EMPTY = {
  country: 'EG',
  province: '',
  city: '',
  street: '',
  radius_km: 5,
  business_types: [],
  max_results: 100,
  priority: 'normal',
}

// Roughly what a job costs to run, so the operator sees it before pressing the
// button rather than in next month's bill. Text Search bills per call and
// returns 20 places each, so cost tracks calls, not results — a deliberately
// conservative estimate that assumes no cell saturates and splits.
function estimateCalls(maxResults, typeCount) {
  return Math.max(1, Math.ceil(maxResults / 20)) + Math.max(0, typeCount - 1)
}

export default function NewSearchModal({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const create = useCreateJob()

  const set = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  function toggleType(value) {
    setForm((current) => ({
      ...current,
      business_types: current.business_types.includes(value)
        ? current.business_types.filter((t) => t !== value)
        : [...current.business_types, value],
    }))
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    try {
      const job = await create.mutateAsync({
        ...form,
        radius_km: Number(form.radius_km),
        max_results: Number(form.max_results),
      })
      onCreated?.(job)
      onClose()
    } catch (err) {
      // The service returns a plain {detail} for a bad address, which is the
      // most common failure and the one worth reading verbatim.
      setError(err?.response?.data?.detail || normalizeError(err).message)
    }
  }

  const valid = form.city.trim() && form.business_types.length > 0
  const calls = estimateCalls(Number(form.max_results), form.business_types.length)

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/60 p-4">
      <form
        onSubmit={submit}
        className="mt-10 w-full max-w-2xl rounded-card bg-surface p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-tx">New search</h2>
            <p className="mt-1 text-sm text-tx-2">
              Finds businesses on Google Places, then enriches and scores them.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-tx-2 hover:text-tx">
            <X size={18} />
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Country">
            <input
              value={form.country}
              onChange={set('country')}
              maxLength={2}
              className={inputClass}
              placeholder="EG"
            />
          </Field>
          <Field label="Governorate">
            <input
              value={form.province}
              onChange={set('province')}
              className={inputClass}
              placeholder="Cairo"
            />
          </Field>
          <Field label="City" required>
            <input
              value={form.city}
              onChange={set('city')}
              className={inputClass}
              placeholder="Cairo"
            />
          </Field>
          <Field label="Area or street">
            <input
              value={form.street}
              onChange={set('street')}
              className={inputClass}
              placeholder="Maadi"
            />
          </Field>
          <Field label="Radius (km)">
            <input
              type="number"
              min={1}
              max={50}
              value={form.radius_km}
              onChange={set('radius_km')}
              className={inputClass}
            />
          </Field>
          <Field label="Priority">
            <select value={form.priority} onChange={set('priority')} className={inputClass}>
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="mt-5">
          <div className="mb-2 text-sm font-medium text-tx">
            Business types <span className="text-danger">*</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {BUSINESS_TYPES.map((type) => {
              const on = form.business_types.includes(type.value)
              return (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => toggleType(type.value)}
                  className={
                    'rounded-full px-3 py-1 text-xs font-semibold transition ' +
                    (on
                      ? 'bg-brand text-white'
                      : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
                  }
                >
                  {type.label}
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-5">
          <Field label="Maximum results">
            <div className="flex flex-wrap gap-2">
              {MAX_RESULTS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setForm((c) => ({ ...c, max_results: value }))}
                  className={
                    'rounded-ctl px-3 py-1.5 text-sm font-semibold transition ' +
                    (Number(form.max_results) === value
                      ? 'bg-brand text-white'
                      : 'bg-surface-2 text-tx-2 hover:bg-surface-3 hover:text-tx')
                  }
                >
                  {value}
                </button>
              ))}
            </div>
          </Field>
        </div>

        {/* Google bills per call, so the operator should see the shape of the
            spend before starting, not after. */}
        <p className="mt-4 rounded-ctl bg-surface-2 px-3 py-2 text-xs text-tx-2">
          Roughly <span className="font-semibold text-tx">{calls}</span> billed Places
          {calls === 1 ? ' call' : ' calls'} at minimum. Dense areas are searched more
          finely, so a busy district can cost more.
        </p>

        {error && (
          <p className="mt-4 rounded-ctl bg-surface-2 px-3 py-2 text-sm text-danger">{error}</p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-ctl px-4 py-2 text-sm text-tx-2 hover:text-tx"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!valid || create.isPending}
            className="inline-flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-d disabled:opacity-50"
          >
            {create.isPending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Start search
          </button>
        </div>
      </form>
    </div>
  )
}

const inputClass =
  'w-full rounded-ctl bg-surface-2 px-3 py-2 text-sm text-tx outline-none ring-brand/50 placeholder:text-tx-2/60 focus:ring-2'

function Field({ label, required, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-tx">
        {label} {required && <span className="text-danger">*</span>}
      </span>
      {children}
    </label>
  )
}
