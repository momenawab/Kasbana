import { useState } from 'react'
import { Loader2, Power, Save } from 'lucide-react'
import { useMaintenance, useSetMaintenance, useSettings, useUpsertSetting } from './api'
import { normalizeError } from '../../lib/api'

export default function SettingsTab({ canManage }) {
  return (
    <div className="flex flex-col gap-6">
      <MaintenanceCard canManage={canManage} />
      <SettingsList canManage={canManage} />
    </div>
  )
}

function MaintenanceCard({ canManage }) {
  const { data, isLoading } = useMaintenance()
  const setMaintenance = useSetMaintenance()
  const [message, setMessage] = useState('')

  if (isLoading || !data) return <Loader2 className="animate-spin text-tx-3" />
  const on = data.enabled

  async function toggle() {
    if (on && !window.confirm('Turn maintenance mode OFF and resume merchant traffic?')) return
    if (!on && !window.confirm('Turn maintenance mode ON? This 503s all merchant traffic.')) return
    try {
      await setMaintenance.mutateAsync({ enabled: !on, message: message || data.message })
    } catch (err) {
      window.alert(normalizeError(err).message)
    }
  }

  return (
    <div
      className={
        'flex flex-col gap-3 rounded-card border p-4 ' +
        (on ? 'border-danger/50 bg-surface' : 'border-line bg-surface')
      }
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-head font-semibold text-tx">Maintenance mode</h2>
          <p className="text-sm text-tx-3">
            {on
              ? 'ON — merchant API is returning 503. The admin console stays reachable.'
              : 'OFF — merchant traffic flowing normally.'}
          </p>
        </div>
        <span
          className={
            'rounded-full px-3 py-1 text-xs font-semibold ' +
            (on ? 'bg-danger/15 text-danger' : 'bg-surface-2 text-tx-3')
          }
        >
          {on ? 'ON' : 'OFF'}
        </span>
      </div>
      {canManage && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={data.message || 'Optional message shown to clients'}
            className="flex-1 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
          />
          <button
            onClick={toggle}
            disabled={setMaintenance.isPending}
            className={
              'flex items-center gap-1.5 rounded-ctl px-3 py-2 text-sm font-semibold disabled:opacity-60 ' +
              (on
                ? 'bg-success text-bg'
                : 'border border-danger/50 text-danger hover:bg-danger hover:text-bg')
            }
          >
            <Power size={15} /> {on ? 'Turn OFF' : 'Turn ON'}
          </button>
        </div>
      )}
    </div>
  )
}

function SettingsList({ canManage }) {
  const { data, isLoading } = useSettings()
  if (isLoading || !data) return <Loader2 className="animate-spin text-tx-3" />

  const visible = data.filter((s) => s.key !== 'maintenance_mode')
  return (
    <div className="flex flex-col gap-3">
      <h2 className="font-head font-semibold text-tx">Platform settings</h2>
      {visible.length === 0 && <p className="text-sm text-tx-3">No settings yet.</p>}
      {visible.map((s) => (
        <SettingRow key={s.key} setting={s} canManage={canManage} />
      ))}
      {canManage && <NewSetting />}
    </div>
  )
}

function SettingRow({ setting, canManage }) {
  const upsert = useUpsertSetting()
  const [text, setText] = useState(JSON.stringify(setting.value, null, 2))
  const [err, setErr] = useState('')

  async function save() {
    let value
    try {
      value = JSON.parse(text)
    } catch {
      setErr('Value must be valid JSON.')
      return
    }
    setErr('')
    try {
      await upsert.mutateAsync({ key: setting.key, body: { value } })
    } catch (e) {
      window.alert(normalizeError(e).message)
    }
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="font-num text-sm text-tx">{setting.key}</div>
      {setting.description && <div className="text-xs text-tx-3">{setting.description}</div>}
      <textarea
        rows={3}
        disabled={!canManage}
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="mt-2 w-full rounded-ctl border border-line bg-bg px-3 py-2 font-num text-xs text-tx focus:border-brand focus:outline-none disabled:opacity-70"
      />
      {err && <p className="text-xs text-danger">{err}</p>}
      {canManage && (
        <button
          onClick={save}
          disabled={upsert.isPending}
          className="mt-2 flex items-center gap-1.5 rounded-ctl border border-line px-3 py-1.5 text-sm text-tx-2 hover:border-brand hover:text-brand disabled:opacity-60"
        >
          <Save size={14} /> Save
        </button>
      )}
    </div>
  )
}

function NewSetting() {
  const upsert = useUpsertSetting()
  const [key, setKey] = useState('')

  async function add() {
    if (!key.trim()) return
    try {
      await upsert.mutateAsync({ key: key.trim(), body: { value: {} } })
      setKey('')
    } catch (e) {
      window.alert(normalizeError(e).message)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <input
        value={key}
        onChange={(e) => setKey(e.target.value)}
        placeholder="new_setting_key"
        className="w-56 rounded-ctl border border-line bg-bg px-3 py-2 text-sm text-tx focus:border-brand focus:outline-none"
      />
      <button
        onClick={add}
        className="rounded-ctl border border-line px-3 py-2 text-sm text-tx-2 hover:border-brand hover:text-brand"
      >
        Add setting
      </button>
    </div>
  )
}
