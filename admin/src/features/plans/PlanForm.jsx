import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useSavePlan } from './api'
import { normalizeError } from '../../lib/api'

const FEATURES = [
  ['export', 'Export'],
  ['api', 'API access'],
  ['specialized_roles', 'Marketing/Designer roles'],
  ['custom_branding', 'Custom branding'],
  ['referral', 'Referral program'],
]

const LIMITS = [
  ['max_cards', 'Max cards'],
  ['max_locations', 'Max locations'],
  ['max_staff', 'Max staff'],
  ['max_customers', 'Max customers'],
]

function blankFrom(plan) {
  return {
    key: plan?.key ?? '',
    name: plan?.name ?? '',
    price_egp: plan?.price_egp ?? '0',
    is_public: plan?.is_public ?? true,
    max_cards: plan?.max_cards ?? '',
    max_locations: plan?.max_locations ?? '',
    max_staff: plan?.max_staff ?? '',
    max_customers: plan?.max_customers ?? '',
    export: plan?.export ?? false,
    api: plan?.api ?? false,
    specialized_roles: plan?.specialized_roles ?? false,
    custom_branding: plan?.custom_branding ?? false,
    referral: plan?.referral ?? false,
    automations: plan?.automations ?? 0,
    analytics: plan?.analytics ?? 'basic',
  }
}

// Blank limit inputs mean "unlimited" (null) — mirrors the backend's None = unlimited.
function toPayload(form) {
  const payload = { ...form }
  for (const key of ['max_cards', 'max_locations', 'max_staff', 'max_customers']) {
    payload[key] = payload[key] === '' ? null : Number(payload[key])
  }
  payload.automations = Number(payload.automations)
  return payload
}

export default function PlanForm({ plan, onDone, onCancel }) {
  const isNew = !plan
  const [form, setForm] = useState(blankFrom(plan))
  const [error, setError] = useState('')
  const save = useSavePlan()

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    try {
      await save.mutateAsync({ ...toPayload(form), isNew })
      onDone()
    } catch (err) {
      setError(normalizeError(err).message)
    }
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-4 rounded-card border border-line bg-surface p-5"
    >
      <h2 className="font-head text-lg font-semibold text-tx">
        {isNew ? 'New plan' : `Edit ${plan.key}`}
      </h2>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm text-tx-2">Key</span>
          <input
            value={form.key}
            disabled={!isNew}
            onChange={(e) => set('key', e.target.value.toUpperCase())}
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand disabled:opacity-60"
            placeholder="ENTERPRISE"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-tx-2">Name</span>
          <input
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm text-tx-2">Price (EGP/mo)</span>
          <input
            type="number"
            step="0.01"
            value={form.price_egp}
            onChange={(e) => set('price_egp', e.target.value)}
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="flex items-center gap-2 pt-6 text-sm text-tx-2">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => set('is_public', e.target.checked)}
          />
          Public (offered at self-serve subscribe)
        </label>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-tx-2">Limits (blank = unlimited)</h3>
        <div className="grid gap-3 sm:grid-cols-4">
          {LIMITS.map(([field, label]) => (
            <label key={field} className="block">
              <span className="mb-1 block text-xs text-tx-3">{label}</span>
              <input
                type="number"
                min="0"
                value={form[field]}
                onChange={(e) => set(field, e.target.value)}
                className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
              />
            </label>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-tx-2">Features</h3>
        <div className="flex flex-wrap gap-4">
          {FEATURES.map(([field, label]) => (
            <label key={field} className="flex items-center gap-2 text-sm text-tx-2">
              <input
                type="checkbox"
                checked={form[field]}
                onChange={(e) => set(field, e.target.checked)}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-xs text-tx-3">Automations</span>
          <input
            type="number"
            min="0"
            value={form.automations}
            onChange={(e) => set('automations', e.target.value)}
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-tx-3">Analytics</span>
          <select
            value={form.analytics}
            onChange={(e) => set('analytics', e.target.value)}
            className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2 text-tx outline-none focus:border-brand"
          >
            <option value="basic">Basic</option>
            <option value="full">Full</option>
          </select>
        </label>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={save.isPending || !form.key || !form.name}
          className="inline-flex items-center gap-2 rounded-ctl bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-d disabled:opacity-60"
        >
          {save.isPending && <Loader2 size={16} className="animate-spin" />}
          {isNew ? 'Create plan' : 'Save changes'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-ctl border border-line px-4 py-2 text-sm text-tx-2 hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
