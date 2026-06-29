// Automations (spec §14) — 5 lifecycle automations, each a Toggle + channel.
// Enabling beyond features.automations opens the UpgradeDrawer.
import { useTranslation } from 'react-i18next'
import { Zap } from 'lucide-react'
import { useAutomations, useUpdateAutomation } from './api'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import { gating } from '../../lib/gating'
import { Toggle } from '../../components/Toggle'
import Badge from '../../components/Badge'
import Skeleton from '../../components/Skeleton'

const KEYS = ['reward_ready', 'expiry', 'birthday', 'winback', 'welcome']

export default function Automations() {
  const { t } = useTranslation()
  const { limit } = usePlan()
  const toast = useToast()
  const { data: automations = [], isLoading } = useAutomations()
  const update = useUpdateAutomation()

  const allowed = limit('automations') // may be undefined → treat as 0 for gating
  const maxAutomations = typeof allowed === 'number' ? allowed : Number(allowed) || 0

  const byKey = Object.fromEntries(automations.map((a) => [a.key, a]))
  const enabledCount = automations.filter((a) => a.enabled).length

  async function toggle(key, current) {
    const turningOn = !current?.enabled
    // Gate: enabling beyond the plan's automation count opens the UpgradeDrawer.
    if (turningOn && enabledCount >= maxAutomations) {
      gating.open('automations')
      return
    }
    try {
      await update.mutateAsync({
        key,
        enabled: turningOn,
        channel: current?.channel || 'PUSH',
        timing: current?.timing || '',
        template: current?.template || '',
      })
    } catch (err) {
      toast.error(normalizeError(err).message)
    }
  }

  if (isLoading) return <Skeleton h={300} rounded="card" />

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-head text-2xl font-bold text-ink">{t('automations.title')}</h1>
      <p className="text-sm text-tx-2">{t('automations.subtitle')}</p>

      <div className="flex flex-col gap-3">
        {KEYS.map((key) => {
          const a = byKey[key]
          return (
            <div key={key} className="flex items-center justify-between rounded-card border border-line bg-white p-4">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-ctl bg-amber-bg text-amber-d">
                  <Zap size={18} />
                </span>
                <div>
                  <div className="font-head font-semibold text-ink">{t(`automations.key.${key}`)}</div>
                  <div className="text-xs text-tx-3">{t(`automations.desc.${key}`)}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {a?.channel && <Badge tone="neutral">{a.channel}</Badge>}
                <Toggle checked={Boolean(a?.enabled)} onChange={() => toggle(key, a)} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
