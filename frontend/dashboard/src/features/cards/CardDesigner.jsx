// Card Designer (spec §14) — two-pane: left form, right live WalletPreview
// (Apple⇄Google). Save draft (DRAFT) / Publish (ACTIVE) → POST or PATCH /cards.
// Unsaved-changes guard; editing a published card warns it re-provisions passes.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCard, useSaveCard } from './api'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import { Input, Textarea } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import WalletPreview from '../../components/WalletPreview'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'

const EMPTY = {
  name: '',
  stamps_required: 8,
  reward_title: '',
  reward_description: '',
  color_bg: '#0E1B2A',
  color_fg: '#FFFFFF',
  logo_url: '',
  hero_image_url: '',
  collect_birthday: false,
}

export default function CardDesigner() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)
  const { merchant } = useAuth()
  const toast = useToast()
  const save = useSaveCard()

  const { data: existing, isLoading } = useCard(id)
  const [form, setForm] = useState(EMPTY)
  const [dirty, setDirty] = useState(false)
  const [platform, setPlatform] = useState('APPLE')
  const [errors, setErrors] = useState({})

  // Seed defaults from the merchant brand (create) or the loaded card (edit).
  useEffect(() => {
    if (isEdit && existing) {
      setForm({ ...EMPTY, ...existing })
    } else if (!isEdit) {
      setForm((f) => ({
        ...f,
        color_bg: merchant?.color_bg || f.color_bg,
        color_fg: merchant?.color_fg || f.color_fg,
        logo_url: merchant?.logo_url || '',
      }))
    }
  }, [isEdit, existing, merchant])

  // Warn on browser-level navigation away with unsaved edits.
  useEffect(() => {
    if (!dirty) return
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const set = (key) => (value) => {
    setForm((f) => ({ ...f, [key]: value }))
    setDirty(true)
  }
  const setEvt = (key) => (e) => set(key)(e.target.value)

  function validate() {
    const errs = {}
    if (!form.name.trim()) errs.name = t('validation.required')
    if (!form.reward_title.trim()) errs.reward_title = t('validation.required')
    const n = Number(form.stamps_required)
    if (!(n >= 1 && n <= 30)) errs.stamps_required = t('designer.stampsRange')
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  async function persist(status) {
    if (!validate()) return
    try {
      const payload = {
        id,
        name: form.name,
        stamps_required: Number(form.stamps_required),
        reward_title: form.reward_title,
        reward_description: form.reward_description,
        color_bg: form.color_bg,
        color_fg: form.color_fg,
        logo_url: form.logo_url || '',
        hero_image_url: form.hero_image_url || '',
        status,
      }
      const card = await save.mutateAsync(payload)
      setDirty(false)
      toast.success(status === 'ACTIVE' ? t('designer.published') : t('designer.savedDraft'))
      navigate(`/cards/${card.id}`)
    } catch (err) {
      const { code, message, fields } = normalizeError(err)
      if (fields) setErrors(fields)
      toast.error(code === 'PLAN_LIMIT' ? t('cards.planLimit') : message)
    }
  }

  function guardedBack() {
    if (dirty && !window.confirm(t('designer.unsaved'))) return
    navigate('/cards')
  }

  if (isEdit && isLoading) {
    return <Skeleton h={400} rounded="card" />
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-ink">
          {isEdit ? t('designer.editTitle') : t('designer.newTitle')}
        </h1>
        <Button variant="ghost" onClick={guardedBack}>
          {t('onboarding.back')}
        </Button>
      </div>

      {isEdit && existing?.status === 'ACTIVE' && (
        <div className="mb-4 rounded-ctl bg-amber-bg px-4 py-2 text-sm text-amber-d">
          {t('designer.reprovisionWarning')}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Form */}
        <div className="flex flex-col gap-4 rounded-card border border-line bg-white p-5">
          <Input
            label={t('onboarding.cardName')}
            value={form.name}
            onChange={setEvt('name')}
            error={errors.name}
          />
          <div>
            <label className="mb-1 block text-sm text-tx-2">{t('designer.stampsRequired')}</label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={1}
                max={30}
                value={form.stamps_required}
                onChange={setEvt('stamps_required')}
                className="flex-1 accent-amber"
              />
              <input
                type="number"
                min={1}
                max={30}
                value={form.stamps_required}
                onChange={setEvt('stamps_required')}
                className="w-16 rounded-ctl border border-line px-2 py-1 text-center font-num"
              />
            </div>
            {errors.stamps_required && (
              <span className="mt-1 block text-xs text-danger">{errors.stamps_required}</span>
            )}
          </div>
          <Input
            label={t('onboarding.rewardTitle')}
            value={form.reward_title}
            onChange={setEvt('reward_title')}
            error={errors.reward_title}
          />
          <Textarea
            label={t('designer.rewardDescription')}
            value={form.reward_description}
            onChange={setEvt('reward_description')}
            rows={2}
          />
          <FileUpload label={t('onboarding.logo')} onUploaded={set('logo_url')} />
          <FileUpload label={t('designer.heroImage')} onUploaded={set('hero_image_url')} />
          <div className="grid grid-cols-2 gap-3">
            <ColorPicker label={t('onboarding.colorBg')} value={form.color_bg} onChange={set('color_bg')} />
            <ColorPicker label={t('onboarding.colorFg')} value={form.color_fg} onChange={set('color_fg')} />
          </div>
          <Toggle
            checked={form.collect_birthday}
            onChange={set('collect_birthday')}
            label={t('designer.collectBirthday')}
          />
          <div className="flex gap-2 pt-2">
            <Button variant="ghost" onClick={() => persist('DRAFT')} loading={save.isPending} className="flex-1">
              {t('designer.saveDraft')}
            </Button>
            <Button onClick={() => persist('ACTIVE')} loading={save.isPending} className="flex-1">
              {t('designer.publish')}
            </Button>
          </div>
        </div>

        {/* Live preview */}
        <div className="flex flex-col items-center gap-3 rounded-card bg-paper p-5">
          <div className="flex gap-2">
            <Button size="sm" variant={platform === 'APPLE' ? 'primary' : 'ghost'} onClick={() => setPlatform('APPLE')}>
              Apple
            </Button>
            <Button size="sm" variant={platform === 'GOOGLE' ? 'primary' : 'ghost'} onClick={() => setPlatform('GOOGLE')}>
              Google
            </Button>
          </div>
          <WalletPreview
            platform={platform}
            logoUrl={form.logo_url}
            colorBg={form.color_bg}
            colorFg={form.color_fg}
            merchantName={merchant?.name || t('app.name')}
            programName={form.name || t('onboarding.cardNamePlaceholder')}
            rewardTitle={form.reward_title || t('onboarding.rewardPlaceholder')}
            stampsRequired={Number(form.stamps_required) || 8}
            stampCount={Math.min(3, Number(form.stamps_required) || 8)}
          />
        </div>
      </div>
    </div>
  )
}
