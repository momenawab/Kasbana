// Registration page & QR editor (finalize Phase 2). Reused for the merchant
// default (no cardId) and a per-card override (cardId). Rich look controls are
// gated behind custom_branding; field/QR/legal controls stay open to all plans.
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import { usePlan } from '../../hooks/usePlan'
import { Input, Textarea, Select } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import Button from '../../components/Button'
import EnrollPreview from './EnrollPreview'
import { useEnrollTheme, useSaveEnrollTheme } from './api'

const EDITABLE = [
  'template_key',
  'cover_image_url',
  'bg_color',
  'accent_color',
  'button_text_color',
  'font',
  'welcome_body',
  'fields_config',
  'qr_style',
  'terms_url',
  'privacy_url',
]

function normalize(theme) {
  const fc = theme.fields_config || {}
  const qr = theme.qr_style || {}
  const field = (k) => ({ show: Boolean(fc[k]?.show), required: Boolean(fc[k]?.required) })
  return {
    template_key: theme.template_key || 'classic',
    cover_image_url: theme.cover_image_url || '',
    bg_color: theme.bg_color || '',
    accent_color: theme.accent_color || '',
    button_text_color: theme.button_text_color || '',
    font: theme.font || 'system',
    welcome_body: theme.welcome_body || '',
    fields_config: {
      phone: field('phone'),
      name: field('name'),
      email: field('email'),
      birthday: field('birthday'),
    },
    qr_style: {
      module_style: qr.module_style || 'square',
      fg_color: qr.fg_color || '',
      bg_color: qr.bg_color || '',
      frame: qr.frame || 'none',
    },
    terms_url: theme.terms_url || '',
    privacy_url: theme.privacy_url || '',
  }
}

// Dims a section and routes clicks to the upgrade drawer when the plan lacks it.
function Lockable({ locked, onUnlock, children }) {
  if (!locked) return children
  return (
    <div className="relative">
      <div className="pointer-events-none select-none opacity-50">{children}</div>
      <button
        type="button"
        onClick={onUnlock}
        className="absolute inset-0 cursor-pointer"
        aria-label="upgrade to unlock"
      />
    </div>
  )
}

function Section({ title, action, children }) {
  return (
    <div className="rounded-ctl border border-line p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-tx">{title}</h3>
        {action}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </div>
  )
}

export default function EnrollThemeEditor({ cardId }) {
  const { t } = useTranslation()
  const toast = useToast()
  const { can, requireFeature } = usePlan()
  const branded = can('custom_branding')

  const { data: theme } = useEnrollTheme(cardId)
  const { data: business } = useQuery({
    queryKey: ['settings', 'business'],
    queryFn: async () => (await api.get('/settings/business')).data,
  })
  const { data: card } = useQuery({
    queryKey: ['cards', cardId],
    queryFn: async () => (await api.get(`/cards/${cardId}`)).data,
    enabled: Boolean(cardId),
  })
  const save = useSaveEnrollTheme(cardId)

  const [form, setForm] = useState(null)
  useEffect(() => {
    if (theme) setForm(normalize(theme))
  }, [theme])

  if (!form) return null

  const brandBg = (cardId ? card?.color_bg : business?.color_bg) || business?.color_bg || '#0E1B2A'
  const brandFg = (cardId ? card?.color_fg : business?.color_fg) || business?.color_fg || '#FFFFFF'
  const logoUrl = (cardId ? card?.logo_url : business?.logo_url) || business?.logo_url || ''
  const merchantName = business?.name || t('enrollTheme.sampleMerchant')
  const programName = card?.name || t('enrollTheme.sampleProgram')
  const rewardTitle = card?.reward_title || t('enrollTheme.sampleReward')

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const setFieldCfg = (key, patch) =>
    setForm((f) => ({
      ...f,
      fields_config: { ...f.fields_config, [key]: { ...f.fields_config[key], ...patch } },
    }))
  const setQr = (patch) => setForm((f) => ({ ...f, qr_style: { ...f.qr_style, ...patch } }))

  const onSave = () => {
    const payload = Object.fromEntries(EDITABLE.map((k) => [k, form[k]]))
    save.mutate(payload, {
      onSuccess: () => toast.success(t('settings.saved')),
      onError: (err) => toast.error(normalizeError(err).message),
    })
  }

  const unlock = () => requireFeature('custom_branding')
  const effective = {
    ...form,
    accent_color: form.accent_color || brandBg,
    button_text_color: form.button_text_color || brandFg,
  }

  const templateOpts = ['classic', 'hero', 'minimal', 'bold'].map((v) => ({
    value: v,
    label: t(`enrollTheme.template_${v}`),
  }))
  const fontOpts = ['system', 'serif', 'rounded'].map((v) => ({
    value: v,
    label: t(`enrollTheme.font_${v}`),
  }))
  const shapeOpts = ['square', 'rounded', 'dots'].map((v) => ({
    value: v,
    label: t(`enrollTheme.shape_${v}`),
  }))
  const frameOpts = ['none', 'scan_to_join', 'collect_stamps'].map((v) => ({
    value: v,
    label: t(`enrollTheme.frame_${v}`),
  }))

  const FieldRow = ({ k, label }) => (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-tx">{label}</span>
      <div className="flex items-center gap-4">
        <Toggle
          checked={form.fields_config[k].show}
          onChange={(v) =>
            setFieldCfg(k, { show: v, required: v ? form.fields_config[k].required : false })
          }
          label={t('enrollTheme.show')}
        />
        <Toggle
          checked={form.fields_config[k].required}
          disabled={!form.fields_config[k].show}
          onChange={(v) => setFieldCfg(k, { required: v })}
          label={t('enrollTheme.required')}
        />
      </div>
    </div>
  )

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Editor column */}
      <div className="flex flex-col gap-4">
        <Section
          title={t('enrollTheme.sectionLook')}
          action={
            !branded && (
              <button type="button" onClick={unlock} className="text-xs text-violet-d underline">
                {t('settings.upgradeToUnlock')}
              </button>
            )
          }
        >
          <Lockable locked={!branded} onUnlock={unlock}>
            <div className="flex flex-col gap-3">
              <Select
                label={t('enrollTheme.template')}
                value={form.template_key}
                options={templateOpts}
                onChange={(e) => setField('template_key', e.target.value)}
              />
              <FileUpload
                label={t('enrollTheme.cover')}
                onUploaded={(url) => setField('cover_image_url', url)}
              />
              <Select
                label={t('enrollTheme.font')}
                value={form.font}
                options={fontOpts}
                onChange={(e) => setField('font', e.target.value)}
              />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <ColorPicker
                    label={t('enrollTheme.accentColor')}
                    value={form.accent_color || brandBg}
                    onChange={(v) => setField('accent_color', v)}
                  />
                  {form.accent_color && (
                    <button
                      type="button"
                      onClick={() => setField('accent_color', '')}
                      className="mt-1 text-xs text-tx-3 underline"
                    >
                      {t('enrollTheme.resetInherit')}
                    </button>
                  )}
                </div>
                <div>
                  <ColorPicker
                    label={t('enrollTheme.buttonTextColor')}
                    value={form.button_text_color || brandFg}
                    onChange={(v) => setField('button_text_color', v)}
                  />
                  {form.button_text_color && (
                    <button
                      type="button"
                      onClick={() => setField('button_text_color', '')}
                      className="mt-1 text-xs text-tx-3 underline"
                    >
                      {t('enrollTheme.resetInherit')}
                    </button>
                  )}
                </div>
              </div>
              <div>
                <ColorPicker
                  label={t('enrollTheme.bgColor')}
                  value={form.bg_color || '#FFFFFF'}
                  onChange={(v) => setField('bg_color', v)}
                />
                {form.bg_color && (
                  <button
                    type="button"
                    onClick={() => setField('bg_color', '')}
                    className="mt-1 text-xs text-tx-3 underline"
                  >
                    {t('enrollTheme.resetDefault')}
                  </button>
                )}
              </div>
              <Textarea
                label={t('enrollTheme.welcome')}
                rows={3}
                maxLength={600}
                value={form.welcome_body}
                onChange={(e) => setField('welcome_body', e.target.value)}
              />
            </div>
          </Lockable>
        </Section>

        <Section title={t('enrollTheme.sectionFields')}>
          <FieldRow k="name" label={t('enroll.name')} />
          <FieldRow k="phone" label={t('enroll.phone')} />
          <FieldRow k="email" label={t('enroll.email')} />
          <FieldRow k="birthday" label={t('enroll.birthday')} />
          <p className="text-xs text-tx-3">{t('enrollTheme.fieldPhoneNote')}</p>
        </Section>

        <Section title={t('enrollTheme.sectionQr')}>
          <Select
            label={t('enrollTheme.qrShape')}
            value={form.qr_style.module_style}
            options={shapeOpts}
            onChange={(e) => setQr({ module_style: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <ColorPicker
              label={t('enrollTheme.qrFg')}
              value={form.qr_style.fg_color || '#000000'}
              onChange={(v) => setQr({ fg_color: v })}
            />
            <ColorPicker
              label={t('enrollTheme.qrBg')}
              value={form.qr_style.bg_color || '#FFFFFF'}
              onChange={(v) => setQr({ bg_color: v })}
            />
          </div>
          <Select
            label={t('enrollTheme.qrFrame')}
            value={form.qr_style.frame}
            options={frameOpts}
            onChange={(e) => setQr({ frame: e.target.value })}
          />
        </Section>

        <Section title={t('enrollTheme.sectionLegal')}>
          <Input
            label={t('enrollTheme.termsUrl')}
            dir="ltr"
            placeholder="https://…"
            value={form.terms_url}
            onChange={(e) => setField('terms_url', e.target.value)}
          />
          <Input
            label={t('enrollTheme.privacyUrl')}
            dir="ltr"
            placeholder="https://…"
            value={form.privacy_url}
            onChange={(e) => setField('privacy_url', e.target.value)}
          />
        </Section>

        <Button onClick={onSave} loading={save.isPending} className="self-start">
          {t('settings.save')}
        </Button>
      </div>

      {/* Preview column — on wide screens it's a full-viewport-height sticky
          rail with the mock centered inside. Because the rail spans the whole
          viewport height (not just the panel's own height), the preview stays
          pinned and fully visible for the entire editor scroll — it rides along
          like a floating layer instead of scrolling out of view near the end.
          `zoom` (not transform:scale) shrinks the real layout box so the whole
          mock (card + QR) fits the viewport height. */}
      <div className="lg:sticky lg:top-20 lg:flex lg:h-[calc(100dvh-6rem)] lg:items-center lg:justify-center lg:self-start">
        <div style={{ zoom: 0.7 }}>
          <EnrollPreview
            theme={effective}
            merchantName={merchantName}
            programName={programName}
            rewardTitle={rewardTitle}
            logoUrl={logoUrl}
          />
        </div>
      </div>
    </div>
  )
}
