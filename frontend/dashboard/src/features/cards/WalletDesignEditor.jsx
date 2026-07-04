// WalletDesignEditor (notes 2-4) — edit the Apple/Google pass variables for one
// card with a faithful dual live preview. Rich controls are gated behind
// custom_branding (free plans keep the smart defaults). Edit-mode only: the
// wallet-design endpoint is per-card, so the card must exist first.
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWalletDesign, useSaveWalletDesign } from './api'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import { Input, Select } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import WalletPreview from '../../components/WalletPreview'
import Button from '../../components/Button'

const REGIONS = {
  apple_header: 3,
  apple_primary: 1,
  apple_secondary: 4,
  apple_auxiliary: 4,
  apple_back: 6,
  google_rows: 3,
}

const DEFAULTS = {
  label_color: '',
  apple_logo_text: '',
  apple_header: [],
  apple_primary: [],
  apple_secondary: [],
  apple_auxiliary: [],
  apple_back: [],
  apple_strip_enabled: true,
  strip_empty_url: '',
  strip_filled_url: '',
  google_title: '',
  google_subtitle: '',
  google_rows: [],
}

const TEXT = '__text__'

// One editable {label, source} row. Custom text is stored as `text:<value>`.
function SlotRow({ slot, onChange, onRemove, tokenOpts, t }) {
  const isText = slot.source.startsWith('text:')
  const sel = isText ? TEXT : slot.source
  return (
    <div className="flex items-end gap-2">
      <div className="flex-1">
        <Input
          label={t('walletDesign.label')}
          value={slot.label}
          onChange={(e) => onChange({ ...slot, label: e.target.value })}
        />
      </div>
      <div className="flex-1">
        <Select
          label={t('walletDesign.value')}
          value={sel}
          onChange={(e) =>
            onChange({ ...slot, source: e.target.value === TEXT ? 'text:' : e.target.value })
          }
          options={[...tokenOpts, { value: TEXT, label: t('walletDesign.tok_text') }]}
        />
      </div>
      {isText && (
        <div className="flex-1">
          <Input
            label={t('walletDesign.customText')}
            value={slot.source.slice(5)}
            onChange={(e) => onChange({ ...slot, source: `text:${e.target.value}` })}
          />
        </div>
      )}
      <Button variant="ghost" size="sm" onClick={onRemove} className="mb-1">
        ✕
      </Button>
    </div>
  )
}

function SlotEditor({ title, slots, cap, onChange, tokenOpts, disabled, t }) {
  const add = () => onChange([...slots, { label: '', source: tokenOpts[0].value }])
  const update = (i, next) => onChange(slots.map((s, j) => (j === i ? next : s)))
  const remove = (i) => onChange(slots.filter((_, j) => j !== i))
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-tx">{title}</span>
        {slots.length < cap && (
          <Button variant="ghost" size="sm" onClick={add} disabled={disabled}>
            + {t('walletDesign.addField')}
          </Button>
        )}
      </div>
      {slots.length === 0 && <p className="text-xs text-tx-3">{t('walletDesign.usingDefault')}</p>}
      {slots.map((s, i) => (
        <SlotRow
          key={i}
          slot={s}
          tokenOpts={tokenOpts}
          t={t}
          onChange={(next) => update(i, next)}
          onRemove={() => remove(i)}
        />
      ))}
    </div>
  )
}

export default function WalletDesignEditor({ cardId, card }) {
  const { t } = useTranslation()
  const toast = useToast()
  const { can, requireFeature } = usePlan()
  const branded = can('custom_branding')
  const { data: loaded } = useWalletDesign(cardId)
  const save = useSaveWalletDesign(cardId)

  const [design, setDesign] = useState(DEFAULTS)
  const [dirty, setDirty] = useState(false)
  const [platform, setPlatform] = useState('APPLE')

  useEffect(() => {
    if (loaded) setDesign({ ...DEFAULTS, ...loaded })
  }, [loaded])

  const set = (key) => (value) => {
    setDesign((d) => ({ ...d, [key]: value }))
    setDirty(true)
  }

  const isStamp = (card?.type ?? 'STAMP') !== 'POINTS'
  const tokenOpts = useMemo(() => {
    const base = isStamp
      ? ['balance', 'stamps', 'goal', 'remaining', 'reward', 'merchant', 'program']
      : ['balance', 'points', 'goal', 'reward', 'merchant', 'program']
    return base.map((v) => ({ value: v, label: t(`walletDesign.tok_${v}`) }))
  }, [isStamp, t])

  const onSave = () => {
    if (!requireFeature('custom_branding')) return
    save.mutate(design, {
      onSuccess: () => {
        setDirty(false)
        toast.success(t('walletDesign.saved'))
      },
      onError: (err) => {
        const { code, message } = normalizeError(err)
        toast.error(code === 'PLAN_LIMIT' ? t('walletDesign.locked') : message)
      },
    })
  }

  const previewProps = {
    design,
    logoUrl: card?.logo_url,
    colorBg: card?.color_bg,
    colorFg: card?.color_fg,
    merchantName: card?.merchantName,
    programName: card?.name,
    rewardTitle: card?.reward_title,
    stampsRequired: Number(card?.stamps_required) || 8,
    stampCount: Math.min(3, Number(card?.stamps_required) || 8),
    cardType: card?.type,
  }

  return (
    <div className="mt-6 rounded-card border border-line bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-head text-lg font-bold text-ink">{t('walletDesign.title')}</h2>
        <Button onClick={onSave} loading={save.isPending} disabled={!dirty}>
          {t('walletDesign.save')}
        </Button>
      </div>

      {!branded && (
        <button
          type="button"
          onClick={() => requireFeature('custom_branding')}
          className="mb-4 w-full rounded-ctl bg-amber-bg px-4 py-2 text-left text-sm text-amber-d"
        >
          {t('walletDesign.upgradeNudge')}
        </button>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Controls */}
        <fieldset disabled={!branded} className="flex flex-col gap-5 disabled:opacity-60">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t('walletDesign.logoText')}
              value={design.apple_logo_text}
              onChange={(e) => set('apple_logo_text')(e.target.value)}
              placeholder={card?.merchantName}
            />
            <ColorPicker
              label={t('walletDesign.labelColor')}
              value={design.label_color || card?.color_fg || '#FFFFFF'}
              onChange={set('label_color')}
            />
          </div>

          {/* Apple */}
          <div className="flex flex-col gap-4 rounded-ctl border border-line p-4">
            <span className="text-xs font-bold uppercase tracking-wide text-tx-3">
              {t('walletDesign.appleSection')}
            </span>
            <SlotEditor
              title={t('walletDesign.header')}
              slots={design.apple_header}
              cap={REGIONS.apple_header}
              tokenOpts={tokenOpts}
              onChange={set('apple_header')}
              disabled={!branded}
              t={t}
            />
            <SlotEditor
              title={t('walletDesign.primary')}
              slots={design.apple_primary}
              cap={REGIONS.apple_primary}
              tokenOpts={tokenOpts}
              onChange={set('apple_primary')}
              disabled={!branded}
              t={t}
            />
            <SlotEditor
              title={t('walletDesign.secondary')}
              slots={design.apple_secondary}
              cap={REGIONS.apple_secondary}
              tokenOpts={tokenOpts}
              onChange={set('apple_secondary')}
              disabled={!branded}
              t={t}
            />
            <SlotEditor
              title={t('walletDesign.auxiliary')}
              slots={design.apple_auxiliary}
              cap={REGIONS.apple_auxiliary}
              tokenOpts={tokenOpts}
              onChange={set('apple_auxiliary')}
              disabled={!branded}
              t={t}
            />
            <SlotEditor
              title={t('walletDesign.back')}
              slots={design.apple_back}
              cap={REGIONS.apple_back}
              tokenOpts={tokenOpts}
              onChange={set('apple_back')}
              disabled={!branded}
              t={t}
            />
            {isStamp && (
              <div className="flex flex-col gap-3 border-t border-line pt-3">
                <Toggle
                  checked={design.apple_strip_enabled}
                  onChange={set('apple_strip_enabled')}
                  label={t('walletDesign.strip')}
                />
                {design.apple_strip_enabled && (
                  <div className="grid grid-cols-2 gap-3">
                    <FileUpload
                      label={t('walletDesign.stripEmpty')}
                      onUploaded={set('strip_empty_url')}
                    />
                    <FileUpload
                      label={t('walletDesign.stripFilled')}
                      onUploaded={set('strip_filled_url')}
                    />
                  </div>
                )}
                <p className="text-xs text-tx-3">{t('walletDesign.stripHint')}</p>
              </div>
            )}
          </div>

          {/* Google */}
          <div className="flex flex-col gap-4 rounded-ctl border border-line p-4">
            <span className="text-xs font-bold uppercase tracking-wide text-tx-3">
              {t('walletDesign.googleSection')}
            </span>
            <div className="grid grid-cols-2 gap-3">
              <Input
                label={t('walletDesign.googleTitle')}
                value={design.google_title}
                onChange={(e) => set('google_title')(e.target.value)}
                placeholder={card?.merchantName}
              />
              <Input
                label={t('walletDesign.googleSubtitle')}
                value={design.google_subtitle}
                onChange={(e) => set('google_subtitle')(e.target.value)}
                placeholder={card?.name}
              />
            </div>
            <SlotEditor
              title={t('walletDesign.googleRows')}
              slots={design.google_rows}
              cap={REGIONS.google_rows}
              tokenOpts={tokenOpts}
              onChange={set('google_rows')}
              disabled={!branded}
              t={t}
            />
          </div>
        </fieldset>

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
          <WalletPreview platform={platform} {...previewProps} />
        </div>
      </div>
    </div>
  )
}
