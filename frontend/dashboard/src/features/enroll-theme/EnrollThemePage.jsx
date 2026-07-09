// Per-card registration page & QR override (finalize Phase 2). Wraps the shared
// editor with an "inherits default / customized" banner + a revert action.
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft } from 'lucide-react'
import Button from '../../components/Button'
import { useToast } from '../../hooks/useToast'
import EnrollThemeEditor from './EnrollThemeEditor'
import { useEnrollTheme, useClearCardEnrollTheme } from './api'

export default function EnrollThemePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const toast = useToast()
  const { data } = useEnrollTheme(id)
  const clear = useClearCardEnrollTheme(id)
  const overridden = Boolean(data?.is_override)

  const revert = () =>
    clear.mutate(undefined, { onSuccess: () => toast.success(t('enrollTheme.cleared')) })

  return (
    <div className="mx-auto max-w-4xl">
      <Button
        variant="ghost"
        iconStart={ArrowLeft}
        onClick={() => navigate(`/cards/${id}/qr`)}
        className="mb-4"
      >
        {t('onboarding.back')}
      </Button>

      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="font-head text-2xl font-bold text-slate">{t('enrollTheme.cardTitle')}</h1>
        {overridden && (
          <Button variant="ghost" size="sm" onClick={revert} loading={clear.isPending}>
            {t('enrollTheme.revertDefault')}
          </Button>
        )}
      </div>

      <p className="mb-4 rounded-ctl border border-line bg-paper px-3 py-2 text-sm text-tx-2">
        {overridden ? t('enrollTheme.bannerCustom') : t('enrollTheme.bannerInherits')}
      </p>

      <EnrollThemeEditor cardId={id} />
    </div>
  )
}
