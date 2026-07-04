// WalletDesignEditor (notes 2-4) — edit the Apple/Google pass variables for one
// card with a faithful dual live preview. Rich controls are gated behind
// custom_branding (free plans keep the smart defaults). Edit-mode only: the
// wallet-design endpoint is per-card, so the card must exist first.
//
// Apple fixes the layout: fields live in four regions (header/primary/secondary/
// auxiliary) and, within a region, render LEFT→RIGHT in list order. So position
// = region + order; there is no free placement. The editor labels each region
// with its on-pass position, lets you reorder within it, and warns before a
// region overflows (Apple truncates silently otherwise).
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

// Hard cap (Apple's limit) + "comfortable" count above which we warn of overflow.
const REGIONS = {
  apple_header: { cap: 3, safe: 2, pos: 'header' },
  apple_primary: { cap: 1, safe: 1, pos: 'primary' },
  apple_secondary: { cap: 4, safe: 3, pos: 'secondary' },
  apple_auxiliary: { cap: 4, safe: 3, pos: 'auxiliary' },
  apple_back: { cap: 6, safe: 6, pos: 'back' },
  google_rows: { cap: 3, safe: 3, pos: 'googleRows' },
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
  strip_bg_color: '',
  strip_empty_url: '',
  strip_filled_url: '',
  google_title: '',
  google_subtitle: '',
  google_rows: [],
  google_stamp_hero: false,
}

const TEXT = '__text__'

// Rough on-pass character budget per field before Apple truncates. Header fields
// are the narrowest; back fields wrap so they're effectively unlimited.
const VALUE_BUDGET = {
  apple_header: 12,
  apple_primary: 16,
  apple_secondary: 14,
  apple_auxiliary: 12,
}

function slotText(slot) {
  return slot.source.startsWith('text:') ? slot.source.slice(5) : ''
}

// Returns a warning string when a region is likely to overflow, else null.
function regionWarning(slots, key, t) {
  const cfg = REGIONS[key]
  if (slots.length > cfg.safe) return t('walletDesign.warnCount', { max: cfg.safe })
  const budget = VALUE_BUDGET[key]
  if (budget) {
    const long = slots.some((s) => slotText(s).length > budget || s.label.length > budget)
    if (long) return t('walletDesign.warnLong')
  }
  return null
}

// One editable {label, source} row with reorder + remove. Custom text -> `text:`.
function SlotRow({ slot, index, count, onChange, onRemove, onMove, tokenOpts, t }) {
  const isText = slot.source.startsWith('text:')
  const sel = isText ? TEXT : slot.source
  return (
    <div className="flex items-end gap-2">
      <div className="flex flex-col">
        <button
          type="button"
          onClick={() => onMove(index, -1)}
          disabled={index === 0}
          className="px-1 text-tx-3 disabled:opacity-30"
          aria-label={t('walletDesign.moveUp')}
        >
          ↑
        </button>
        <button
          type="button"
          onClick={() => onMove(index, 1)}
          disabled={index === count - 1}
          className="px-1 text-tx-3 disabled:opacity-30"
          aria-label={t('walletDesign.moveDown')}
        >
          ↓
        </button>
      </div>
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

function SlotEditor({ regionKey, slots, onChange, tokenOpts, disabled, t }) {
  const cfg = REGIONS[regionKey]
  const warning = regionWarning(slots, regionKey, t)
  const add = () => onChange([...slots, { label: '', source: tokenOpts[0].value }])
  const update = (i, next) => onChange(slots.map((s, j) => (j === i ? next : s)))
  const remove = (i) => onChange(slots.filter((_, j) => j !== i))
  const move = (i, dir) => {
    const j = i + dir
    if (j < 0 || j >= slots.length) return
    const next = slots.slice()
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-tx">{t(`walletDesign.${cfg.pos}`)}</span>
          <span className="ml-2 text-xs text-tx-3">{t(`walletDesign.pos_${cfg.pos}`)}</span>
        </div>
        {slots.length < cfg.cap && (
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
          index={i}
          count={slots.length}
          tokenOpts={tokenOpts}
          t={t}
          onChange={(next) => update(i, next)}
          onRemove={() => remove(i)}
          onMove={move}
        />
      ))}
      {warning && (
        <p className="rounded-ctl bg-amber-bg px-2 py-1 text-xs text-amber-d">⚠ {warning}</p>
      )}
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

  const appleRegions = [
    'apple_header',
    'apple_primary',
    'apple_secondary',
    'apple_auxiliary',
    'apple_back',
  ]

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

      <p className="mb-4 rounded-ctl bg-paper px-3 py-2 text-xs text-tx-3">
        {t('walletDesign.layoutNote')}
      </p>

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
            {appleRegions.map((key) => (
              <SlotEditor
                key={key}
                regionKey={key}
                slots={design[key]}
                tokenOpts={tokenOpts}
                onChange={set(key)}
                disabled={!branded}
                t={t}
              />
            ))}
            {isStamp && (
              <div className="flex flex-col gap-3 border-t border-line pt-3">
                <Toggle
                  checked={design.apple_strip_enabled}
                  onChange={set('apple_strip_enabled')}
                  label={t('walletDesign.strip')}
                />
                {design.apple_strip_enabled && (
                  <>
                    <ColorPicker
                      label={t('walletDesign.stripBg')}
                      value={design.strip_bg_color || card?.color_bg || '#0E1B2A'}
                      onChange={set('strip_bg_color')}
                    />
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
                    <p className="text-xs text-tx-3">{t('walletDesign.stripHint')}</p>
                  </>
                )}
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
              regionKey="google_rows"
              slots={design.google_rows}
              tokenOpts={tokenOpts}
              onChange={set('google_rows')}
              disabled={!branded}
              t={t}
            />
            {isStamp && (
              <div className="flex flex-col gap-1 border-t border-line pt-3">
                <Toggle
                  checked={design.google_stamp_hero}
                  onChange={set('google_stamp_hero')}
                  label={t('walletDesign.googleStampHero')}
                />
                <p className="text-xs text-tx-3">{t('walletDesign.googleStampHeroHint')}</p>
              </div>
            )}
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
