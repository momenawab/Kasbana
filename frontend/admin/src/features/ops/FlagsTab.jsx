import { useState } from 'react'
import { Loader2, Plus, X } from 'lucide-react'
import { useFlags, useCreateFlag, useUpdateFlag, useSetOverride, useClearOverride } from './api'
import { normalizeError } from '../../lib/api'

export default function FlagsTab({ canManage }) {
  const { data: flags, isLoading } = useFlags()
  const createFlag = useCreateFlag()
  const updateFlag = useUpdateFlag()
  const setOverride = useSetOverride()
  const clearOverride = useClearOverride()
  const [form, setForm] = useState({ key: '', label: '', enabled: false })

  if (isLoading || !flags) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  async function submit(e) {
    e.preventDefault()
    try {
      await createFlag.mutateAsync({
        key: form.key.trim(),
        label: form.label,
        enabled: form.enabled,
      })
      setForm({ key: '', label: '', enabled: false })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  async function toggle(flag) {
    try {
      await updateFlag.mutateAsync({ key: flag.key, patch: { enabled: !flag.enabled } })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  async function addOverride(flag) {
    const merchant_id = window.prompt(`Merchant ID to override "${flag.key}" for:`)
    if (!merchant_id) return
    const on = window.confirm('OK = enable for this merchant, Cancel = disable')
    try {
      await setOverride.mutateAsync({
        key: flag.key,
        body: { merchant_id: merchant_id.trim(), enabled: on },
      })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {canManage && (
        <form
          onSubmit={submit}
          className="flex flex-wrap items-end gap-3 rounded-card border border-line bg-surface p-4"
        >
          <label className="flex flex-col gap-1 text-xs text-tx-3">
            Key
            <input
              required
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              placeholder="new_dashboard"
              className="w-48 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-tx-3">
            Label
            <input
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              className="w-48 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-tx-2">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            enabled
          </label>
          <button
            type="submit"
            className="flex items-center gap-1.5 rounded-ctl bg-brand px-3 py-2 text-sm font-semibold text-bg"
          >
            <Plus size={15} /> Add flag
          </button>
        </form>
      )}

      <div className="flex flex-col gap-3">
        {flags.length === 0 && <p className="text-sm text-tx-3">No feature flags yet.</p>}
        {flags.map((flag) => (
          <div key={flag.key} className="rounded-card border border-line bg-surface p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="font-num text-tx">{flag.key}</div>
                {flag.label && <div className="text-xs text-tx-3">{flag.label}</div>}
              </div>
              <button
                disabled={!canManage || updateFlag.isPending}
                onClick={() => toggle(flag)}
                className={
                  'rounded-full px-3 py-1 text-xs font-semibold disabled:opacity-50 ' +
                  (flag.enabled ? 'bg-success/15 text-success' : 'bg-surface-2 text-tx-3')
                }
              >
                {flag.enabled ? 'ON' : 'OFF'}
              </button>
            </div>

            {(flag.overrides?.length > 0 || canManage) && (
              <div className="mt-3 border-t border-line pt-3">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-xs text-tx-3">Per-merchant overrides</span>
                  {canManage && (
                    <button
                      onClick={() => addOverride(flag)}
                      className="text-xs text-brand hover:underline"
                    >
                      + add
                    </button>
                  )}
                </div>
                {flag.overrides?.length === 0 && <p className="text-xs text-tx-3">None.</p>}
                <div className="flex flex-col gap-1">
                  {flag.overrides?.map((o) => (
                    <div key={o.merchant_id} className="flex items-center gap-2 text-xs">
                      <span className="font-num text-tx-3">{o.merchant_id}</span>
                      <span className={o.enabled ? 'text-success' : 'text-tx-3'}>
                        {o.enabled ? 'on' : 'off'}
                      </span>
                      {canManage && (
                        <button
                          onClick={() =>
                            clearOverride.mutateAsync({ key: flag.key, merchant_id: o.merchant_id })
                          }
                          className="text-tx-3 hover:text-danger"
                        >
                          <X size={13} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
