// UpgradeDrawer (spec §10/§12) — opened by the global gating store. Shows the
// locked feature + CTA → /billing. Any locked control or a server PLAN_LIMIT
// opens it via gating.open().
import { useSyncExternalStore } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Lock } from 'lucide-react'
import { gating } from '../lib/gating'
import { Drawer } from './Modal'
import Button from './Button'

export default function UpgradeDrawer() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const snap = useSyncExternalStore(gating.subscribe, gating.getSnapshot)

  return (
    <Drawer open={snap.open} onClose={gating.close} title={t('upgrade.title', 'Upgrade your plan')}>
      <div className="flex flex-col items-center gap-4 py-4 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-bg text-amber-d">
          <Lock size={22} />
        </span>
        <p className="text-tx-2">
          {snap.feature
            ? t('upgrade.locked', {
                feature: snap.feature,
                defaultValue: `"${snap.feature}" needs a higher plan.`,
              })
            : t('upgrade.body', 'This feature needs a higher plan.')}
        </p>
        <Button
          onClick={() => {
            gating.close()
            navigate('/billing')
          }}
        >
          {t('upgrade.cta', 'See plans')}
        </Button>
      </div>
    </Drawer>
  )
}
