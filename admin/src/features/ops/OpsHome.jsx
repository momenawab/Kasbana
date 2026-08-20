import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import HealthTab from './HealthTab'
import FlagsTab from './FlagsTab'
import SettingsTab from './SettingsTab'
import JobsTab from './JobsTab'
import WebhooksTab from './WebhooksTab'
import WalletTab from './WalletTab'

const TABS = [
  { key: 'health', label: 'Health' },
  { key: 'flags', label: 'Feature Flags' },
  { key: 'settings', label: 'Settings' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'webhooks', label: 'Webhooks' },
  { key: 'wallet', label: 'Wallet Sync' },
]

const OPS_ROLES = ['SUPER_ADMIN', 'ENGINEERING']

export default function OpsHome() {
  const { role } = useAuth()
  const canManage = OPS_ROLES.includes(role)
  const [tab, setTab] = useState('health')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">Platform Operations</h1>
        {!canManage && (
          <span className="text-xs text-tx-3">
            Read-only — actions need Engineering/Super-admin
          </span>
        )}
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={
              'relative whitespace-nowrap px-3 py-2 text-sm ' +
              (tab === t.key ? 'text-brand' : 'text-tx-3 hover:text-tx-2')
            }
          >
            {t.label}
            {tab === t.key && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-brand" />}
          </button>
        ))}
      </div>

      {tab === 'health' && <HealthTab />}
      {tab === 'flags' && <FlagsTab canManage={canManage} />}
      {tab === 'settings' && <SettingsTab canManage={canManage} />}
      {tab === 'jobs' && <JobsTab canManage={canManage} />}
      {tab === 'webhooks' && <WebhooksTab canManage={canManage} />}
      {tab === 'wallet' && <WalletTab canManage={canManage} />}
    </div>
  )
}
