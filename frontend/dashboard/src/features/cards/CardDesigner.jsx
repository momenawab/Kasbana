// Card Designer (spec §14) — two-pane: left form, right live WalletPreview
// (Apple⇄Google). Save draft (DRAFT) / Publish (ACTIVE) → POST or PATCH /cards.
// Unsaved-changes guard; editing a published card warns it re-provisions passes.
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useCard, useSaveCard } from './api'
import { useAuth } from '../../hooks/useAuth'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import api, { normalizeError } from '../../lib/api'
import { Input, Textarea, Select } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import WalletPreview from '../../components/WalletPreview'
import { STAMP_ICONS } from '../../components/stampIcons'
import StampGlyph from '../../components/StampGlyph'
import WalletDesignEditor from './WalletDesignEditor'
import TemplatePicker from './TemplatePicker'
import { TEMPLATE_SEED } from './templateSeeds'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'

const EMPTY = {
  type: 'STAMP',
  name: '',
  stamps_required: 8,
  reward_title: '',
  reward_description: '',
  color_bg: '#0E1B2A',
  color_fg: '#FFFFFF',
  logo_url: '',
  hero_image_url: '',
  single_use: false,
  referral_enabled: false,
  collect_birthday: false,
}

// Create-time stamp styling — persisted to the card's wallet design after the
// card is created (edit mode uses the full WalletDesignEditor instead).
const EMPTY_STAMP = { stamp_icon: '', stamp_color: '', strip_empty_url: '', strip_filled_url: '' }

// The default locked template per card type (matches the backend + the design
// editor) so the stamp fields land in an editable template on the stored design.
const DEFAULT_TEMPLATE_KEY = { STAMP: 'loyalty_stamps', POINTS: 'points_reward' }

export default function CardDesigner() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const isEdit = Boolean(id)
  const { merchant } = useAuth()
  const { can, requireFeature } = usePlan()
  const branded = can('custom_branding')
  const toast = useToast()
  const save = useSaveCard()

  const { data: existing, isLoading } = useCard(id)
  const [form, setForm] = useState(EMPTY)
  const [stamp, setStamp] = useState(EMPTY_STAMP)
  const [dirty, setDirty] = useState(false)
  const [platform, setPlatform] = useState('APPLE')
  const [errors, setErrors] = useState({})
  // New-card template picker: pickerDone gates the picker → form transition
  // (edit mode skips it entirely). templateId records the chosen starting design.
  const [templateId, setTemplateId] = useState(null)
  const [pickerDone, setPickerDone] = useState(isEdit)

  // Seed defaults from the merchant brand (create) or the loaded card (edit).
  useEffect(() => {
    if (isEdit && existing) {
      setForm({ ...EMPTY, ...existing })
    } else if (!isEdit && !templateId) {
      // Seed the merchant's brand colors only until a template is chosen — the
      // template's own seed (applied in chooseTemplate) takes precedence after.
      setForm((f) => ({
        ...f,
        color_bg: merchant?.color_bg || f.color_bg,
        color_fg: merchant?.color_fg || f.color_fg,
        logo_url: merchant?.logo_url || '',
      }))
    }
  }, [isEdit, existing, merchant, templateId])

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
  const setStampField = (key) => (value) => {
    setStamp((s) => ({ ...s, [key]: value }))
    setDirty(true)
  }

  // The stamp design is worth persisting only when the merchant actually picked
  // an icon/color or uploaded a custom pair (blank = the default drawn circles).
  const hasStampDesign =
    Boolean(stamp.stamp_icon || stamp.stamp_color) ||
    Boolean(stamp.strip_empty_url && stamp.strip_filled_url)

  // Apply a chosen template's seed over the current form, then reveal the form.
  function chooseTemplate(id) {
    const seed = TEMPLATE_SEED[id] || {}
    setForm((f) => ({ ...f, logo_url: merchant?.logo_url || f.logo_url, ...seed }))
    setTemplateId(id)
    setPickerDone(true)
  }

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
        type: form.type,
        name: form.name,
        stamps_required: Number(form.stamps_required),
        reward_title: form.reward_title,
        reward_description: form.reward_description,
        color_bg: form.color_bg,
        color_fg: form.color_fg,
        logo_url: form.logo_url || '',
        hero_image_url: form.hero_image_url || '',
        single_use: form.single_use,
        referral_enabled: form.referral_enabled,
        status,
      }
      const card = await save.mutateAsync(payload)
      // On create, persist the chosen stamp style onto the new card's wallet
      // design (premium only — the endpoint enforces custom_branding). Best-effort:
      // a design failure shouldn't lose the saved card, so surface it and go on.
      if (!isEdit && branded && form.type === 'STAMP' && hasStampDesign) {
        try {
          await api.patch(`/cards/${card.id}/wallet-design`, {
            template_key: DEFAULT_TEMPLATE_KEY.STAMP,
            stamp_icon: stamp.stamp_icon,
            stamp_color: stamp.stamp_color,
            strip_empty_url: stamp.strip_empty_url,
            strip_filled_url: stamp.strip_filled_url,
          })
        } catch {
          toast.error(t('designer.stampSaveFailed'))
        }
      }
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

  // New-card flow starts on the template picker until one is chosen or skipped.
  if (!isEdit && !pickerDone) {
    return <TemplatePicker onChoose={chooseTemplate} onSkip={() => setPickerDone(true)} />
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-ink">
          {isEdit ? t('designer.editTitle') : t('designer.newTitle')}
        </h1>
        <div className="flex items-center gap-2">
          {!isEdit && templateId && (
            <Button variant="ghost" onClick={() => setPickerDone(false)}>
              {t('templatePicker.change')}
            </Button>
          )}
          <Button variant="ghost" onClick={guardedBack}>
            {t('onboarding.back')}
          </Button>
        </div>
      </div>

      {isEdit && existing?.status === 'ACTIVE' && (
        <div className="mb-4 rounded-ctl bg-amber-bg px-4 py-2 text-sm text-amber-d">
          {t('designer.reprovisionWarning')}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Form */}
        <div className="flex flex-col gap-4 rounded-card border border-line bg-white p-5">
          <Select
            name="type"
            label={t('designer.cardType')}
            value={form.type}
            onChange={setEvt('type')}
            options={[
              { value: 'STAMP', label: t('designer.typeStamp') },
              { value: 'POINTS', label: t('designer.typePoints') },
            ]}
          />
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
            <ColorPicker
              label={t('onboarding.colorBg')}
              value={form.color_bg}
              onChange={set('color_bg')}
            />
            <ColorPicker
              label={t('onboarding.colorFg')}
              value={form.color_fg}
              onChange={set('color_fg')}
            />
          </div>

          {/* Stamp style — pick a built-in icon + fill color (or upload your own).
              Create-mode + STAMP only; edit mode uses the full design editor
              below. Premium (custom_branding); free plans keep drawn circles. */}
          {!isEdit && form.type === 'STAMP' && (
            <div className="rounded-ctl border border-line p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-tx">{t('designer.stampStyle')}</span>
                {!branded && (
                  <button
                    type="button"
                    onClick={() => requireFeature('custom_branding')}
                    className="rounded-full bg-amber-bg px-2 py-0.5 text-xs text-amber-d"
                  >
                    {t('designer.premium')}
                  </button>
                )}
              </div>
              <fieldset disabled={!branded} className="flex flex-col gap-3 disabled:opacity-60">
                <div>
                  <label className="mb-1 block text-sm text-tx-2">{t('designer.stampIcon')}</label>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => setStampField('stamp_icon')('')}
                      className={`flex h-9 items-center rounded-ctl border px-2 text-xs ${
                        stamp.stamp_icon
                          ? 'border-line text-tx-3 hover:border-tx-3'
                          : 'border-primary text-primary ring-1 ring-primary'
                      }`}
                    >
                      {t('designer.stampNone')}
                    </button>
                    {STAMP_ICONS.map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        title={label}
                        aria-pressed={stamp.stamp_icon === key}
                        onClick={() => setStampField('stamp_icon')(key)}
                        className={`flex h-9 w-9 items-center justify-center rounded-ctl border transition ${
                          stamp.stamp_icon === key
                            ? 'border-primary ring-1 ring-primary'
                            : 'border-line hover:border-tx-3'
                        }`}
                      >
                        <StampGlyph
                          icon={key}
                          filled
                          color={stamp.stamp_color || form.color_fg}
                          size={20}
                        />
                      </button>
                    ))}
                  </div>
                </div>
                <ColorPicker
                  label={t('designer.stampColor')}
                  value={stamp.stamp_color || form.color_fg}
                  onChange={setStampField('stamp_color')}
                />
                <div>
                  <span className="mb-1 block text-xs text-tx-3">
                    {t('designer.stampUploadHint')}
                  </span>
                  <div className="grid grid-cols-2 gap-3">
                    <FileUpload
                      label={t('walletDesign.stripEmpty')}
                      onUploaded={setStampField('strip_empty_url')}
                    />
                    <FileUpload
                      label={t('walletDesign.stripFilled')}
                      onUploaded={setStampField('strip_filled_url')}
                    />
                  </div>
                </div>
              </fieldset>
            </div>
          )}

          <Toggle
            checked={form.collect_birthday}
            onChange={set('collect_birthday')}
            label={t('designer.collectBirthday')}
          />
          <div>
            <Toggle
              checked={form.single_use}
              onChange={set('single_use')}
              label={t('designer.singleUse')}
            />
            <p className="mt-1 text-xs text-tx-3">{t('designer.singleUseHint')}</p>
          </div>
          <div>
            <Toggle
              checked={form.referral_enabled}
              onChange={set('referral_enabled')}
              label={t('designer.referral')}
            />
            <p className="mt-1 text-xs text-tx-3">{t('designer.referralHint')}</p>
          </div>
          <div className="flex gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => persist('DRAFT')}
              loading={save.isPending}
              className="flex-1"
            >
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
            <Button
              size="sm"
              variant={platform === 'APPLE' ? 'primary' : 'ghost'}
              onClick={() => setPlatform('APPLE')}
            >
              Apple
            </Button>
            <Button
              size="sm"
              variant={platform === 'GOOGLE' ? 'primary' : 'ghost'}
              onClick={() => setPlatform('GOOGLE')}
            >
              Google
            </Button>
          </div>
          <WalletPreview
            platform={platform}
            design={
              !isEdit && form.type === 'STAMP' && hasStampDesign
                ? { ...stamp, apple_strip_enabled: true, google_stamp_hero: true }
                : null
            }
            cardType={form.type}
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

      {/* Wallet pass design (notes 2-4) — edit-mode only (needs a saved card). */}
      {isEdit ? (
        <WalletDesignEditor cardId={id} card={{ ...form, merchantName: merchant?.name }} />
      ) : (
        <p className="mt-6 rounded-card border border-line bg-paper p-4 text-center text-sm text-tx-3">
          {t('walletDesign.saveFirst')}
        </p>
      )}
    </div>
  )
}
