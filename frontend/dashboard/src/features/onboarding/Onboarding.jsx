// Onboarding (spec §14) — 3-step Stepper:
//   1) branding   → PATCH /settings/business (logo, colors)
//   2) first card  → POST /cards (ACTIVE)
//   3) done        → QR (GET /cards/{id}/qr) + WalletPreview
// Skippable; live WalletPreview reflects branding + card fields throughout.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import api, { normalizeError } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import Stepper from '../../components/Stepper'
import { Input } from '../../components/Field'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import WalletPreview from '../../components/WalletPreview'
import QrBlock from '../../components/QrBlock'
import Button from '../../components/Button'

export default function Onboarding() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const { merchant } = useAuth()

  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)

  // Branding (seeded from merchant brand if present).
  const [logoUrl, setLogoUrl] = useState(merchant?.logo_url || '')
  const [colorBg, setColorBg] = useState(merchant?.color_bg || '#0E1B2A')
  const [colorFg, setColorFg] = useState(merchant?.color_fg || '#FFFFFF')

  // First card.
  const [cardName, setCardName] = useState('')
  const [stampsRequired, setStampsRequired] = useState(8)
  const [rewardTitle, setRewardTitle] = useState('')

  // Result (the created card's QR assets).
  const [qr, setQr] = useState(null)

  const steps = [t('onboarding.step1'), t('onboarding.step2'), t('onboarding.step3')]

  async function saveBranding() {
    setBusy(true)
    try {
      await api.patch('/settings/business', {
        logo_url: logoUrl || null,
        color_bg: colorBg,
        color_fg: colorFg,
      })
      await qc.invalidateQueries({ queryKey: ['me'] })
      setStep(1)
    } catch (err) {
      toast.error(normalizeError(err).message)
    } finally {
      setBusy(false)
    }
  }

  async function createCard() {
    if (!cardName || !rewardTitle) {
      toast.error(t('onboarding.cardRequired'))
      return
    }
    setBusy(true)
    try {
      const { data: card } = await api.post('/cards', {
        name: cardName,
        stamps_required: Number(stampsRequired),
        reward_title: rewardTitle,
        color_bg: colorBg,
        color_fg: colorFg,
        logo_url: logoUrl || null,
        status: 'ACTIVE',
      })
      try {
        const { data: qrData } = await api.get(`/cards/${card.id}/qr`)
        setQr(qrData)
      } catch {
        // QR backend (1.6) may be mocked/unavailable — step 3 still shows the preview.
      }
      setStep(2)
    } catch (err) {
      const { code, message } = normalizeError(err)
      toast.error(code === 'PLAN_LIMIT' ? t('onboarding.planLimit') : message)
    } finally {
      setBusy(false)
    }
  }

  const preview = (
    <WalletPreview
      platform="APPLE"
      logoUrl={logoUrl}
      colorBg={colorBg}
      colorFg={colorFg}
      merchantName={merchant?.name || t('app.name')}
      programName={cardName || t('onboarding.cardNamePlaceholder')}
      rewardTitle={rewardTitle || t('onboarding.rewardPlaceholder')}
      stampsRequired={Number(stampsRequired) || 8}
      stampCount={0}
    />
  )

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-slate">{t('onboarding.title')}</h1>
        <button onClick={() => navigate('/')} className="text-sm text-tx-2 hover:text-slate">
          {t('onboarding.skip')}
        </button>
      </div>

      <div className="mb-6">
        <Stepper steps={steps} current={step} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="rounded-card border border-line bg-white p-5">
          {step === 0 && (
            <div className="flex flex-col gap-4">
              <h2 className="font-head font-semibold text-slate">{t('onboarding.brandingTitle')}</h2>
              <FileUpload label={t('onboarding.logo')} onUploaded={setLogoUrl} />
              <ColorPicker label={t('onboarding.colorBg')} value={colorBg} onChange={setColorBg} />
              <ColorPicker label={t('onboarding.colorFg')} value={colorFg} onChange={setColorFg} />
              <Button onClick={saveBranding} loading={busy} className="w-full">
                {t('onboarding.next')}
              </Button>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-4">
              <h2 className="font-head font-semibold text-slate">{t('onboarding.cardTitle')}</h2>
              <Input
                label={t('onboarding.cardName')}
                value={cardName}
                onChange={(e) => setCardName(e.target.value)}
              />
              <Input
                label={t('onboarding.stampsRequired')}
                type="number"
                min={1}
                max={30}
                value={stampsRequired}
                onChange={(e) => setStampsRequired(e.target.value)}
              />
              <Input
                label={t('onboarding.rewardTitle')}
                value={rewardTitle}
                onChange={(e) => setRewardTitle(e.target.value)}
              />
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setStep(0)} className="flex-1">
                  {t('onboarding.back')}
                </Button>
                <Button onClick={createCard} loading={busy} className="flex-1">
                  {t('onboarding.publish')}
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col items-center gap-4 text-center">
              <h2 className="font-head font-semibold text-slate">{t('onboarding.doneTitle')}</h2>
              <p className="text-sm text-tx-2">{t('onboarding.doneBody')}</p>
              {qr?.join_url && <QrBlock value={qr.join_url} />}
              <Button onClick={() => navigate('/')} className="w-full">
                {t('onboarding.goDashboard')}
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-start justify-center rounded-card bg-paper p-5">{preview}</div>
      </div>
    </div>
  )
}
