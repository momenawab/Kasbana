// WalletDesignEditor (templates-only) — pick a layout-locked template and edit
// only that template's `editable` variables (colors, stamp style, a bottom
// image) for one card, with a faithful dual live preview. Positions are always
// hardcoded by the template; the merchant can never move fields. Rich controls
// are gated behind custom_branding (free plans keep the smart defaults).
//
// Two modes:
//   edit   — `cardId` given: loads + saves the design itself, own Save button.
//   create — `value`/`onChange` given and no cardId: the card doesn't exist yet, so
//            the parent owns the state and persists it right after POST /cards. This
//            is what lets the whole design be set at create time instead of forcing
//            a save-then-go-edit round trip.
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useWalletDesign, useSaveWalletDesign, useWalletTemplates } from './api'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import WalletPreview from '../../components/WalletPreview'
import { DEFAULTS } from './walletDesignDefaults'
import { STAMP_ICONS } from '../../components/stampIcons'
import StampGlyph from '../../components/StampGlyph'
import Button from '../../components/Button'

// The default locked template per card type — must match the backend
// (wallets.templates._DEFAULT_BY_TYPE) so a legacy `custom`/unknown key resolves
// to the same layout the pass actually renders.
const DEFAULT_TEMPLATE_KEY = { STAMP: 'loyalty_stamps', POINTS: 'points_reward' }

// How the stamps are arranged. Blank = the backend default (row-major). Only has
// a visible effect once the card wraps to two rows, i.e. more than 5 stamps.
const STAMP_LAYOUTS = ['', 'columns', 'stagger']

// A six-dot thumbnail of each arrangement, so the merchant picks by shape instead
// of by reading a word. Mirrors stampGeometry() in WalletPreview and _centers() in
// wallets/stamp_grid.py: grid runs across (0,1,2 / 3,4,5), the other two alternate
// down (0,2,4 / 1,3,5), and stagger additionally offsets the lower row.
function StampLayoutGlyph({ layout, color }) {
  const alternating = layout === 'columns' || layout === 'stagger'
  const rows = alternating
    ? [
        [0, 2, 4],
        [1, 3, 5],
      ]
    : [
        [0, 1, 2],
        [3, 4, 5],
      ]
  return (
    <span className="flex flex-col gap-0.5" aria-hidden="true">
      {rows.map((row, r) => (
        <span
          key={r}
          className="flex gap-0.5"
          style={layout === 'stagger' && r > 0 ? { marginInlineStart: '4px' } : undefined}
        >
          {row.map((i) => (
            <span key={i} className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
          ))}
        </span>
      ))}
    </span>
  )
}

// A compact gallery thumbnail for one template — a tiny pass mock showing its
// bottom-visual placement (stamps grid / image / none).
function TemplateThumb({ tpl, colorBg, colorFg }) {
  const isImage = tpl.bottom_visual === 'image'
  const isStamps = tpl.bottom_visual === 'stamps'
  return (
    <div
      className="flex h-20 w-full flex-col justify-between rounded-md p-1.5"
      style={{ background: colorBg, color: colorFg }}
    >
      <div className="flex items-center justify-between">
        <span className="h-3 w-3 rounded-sm bg-white/40" />
        <span className="h-1.5 w-8 rounded-full bg-white/40" />
      </div>
      {isStamps && (
        <div className="flex gap-0.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <span
              key={i}
              className="h-2 w-2 rounded-full"
              style={{
                background: i < 2 ? colorFg : 'transparent',
                border: `1px solid ${colorFg}`,
              }}
            />
          ))}
        </div>
      )}
      {isImage && <div className="h-5 w-full rounded-sm bg-white/25" />}
      <div className="h-2.5 w-full self-center rounded-sm bg-white/80" />
    </div>
  )
}

export default function WalletDesignEditor({ cardId, card, value, onChange }) {
  const { t } = useTranslation()
  const toast = useToast()
  const { can, requireFeature } = usePlan()
  const branded = can('custom_branding')
  const { data: loaded } = useWalletDesign(cardId) // no-op without a cardId
  const { data: tplData } = useWalletTemplates()
  const save = useSaveWalletDesign(cardId)

  const templates = useMemo(() => tplData?.templates || [], [tplData])
  const platformLogoUrl = tplData?.platform_logo_url || ''
  const platformLabel = tplData?.platform_label ?? 'Stampn'

  // Controlled (create) vs self-owned (edit) — see the header comment.
  const controlled = typeof onChange === 'function'
  const [own, setOwn] = useState(DEFAULTS)
  const design = controlled ? value : own
  const setDesign = controlled ? onChange : setOwn

  const [dirty, setDirty] = useState(false)
  const [platform, setPlatform] = useState('APPLE')

  useEffect(() => {
    if (loaded) setOwn({ ...DEFAULTS, ...loaded })
  }, [loaded])

  const set = (key) => (v) => {
    setDesign((d) => ({ ...d, [key]: v }))
    setDirty(true)
  }

  const cardType = card?.type ?? 'STAMP'

  const availableTemplates = useMemo(
    () => templates.filter((tpl) => (tpl.card_types || []).includes(cardType)),
    [templates, cardType]
  )

  // The default locked template for this card type (falls back to the first
  // available template if the preferred key isn't in the catalog).
  const defaultTemplateKey = useMemo(() => {
    const preferred = DEFAULT_TEMPLATE_KEY[cardType]
    if (availableTemplates.some((tpl) => tpl.key === preferred)) return preferred
    return availableTemplates[0]?.key || preferred || 'minimal'
  }, [cardType, availableTemplates])

  // Templates-only: a legacy `custom`/unknown/missing key resolves to the locked
  // default, so there is never a freeform state to render. DERIVED, never written
  // back — writing it on load would mark a pristine create form dirty before the
  // merchant has touched anything, and the backend resolves a blank key to this
  // same default anyway (wallets.templates.resolve_template).
  const templateKey = useMemo(
    () =>
      availableTemplates.some((tpl) => tpl.key === design.template_key)
        ? design.template_key
        : defaultTemplateKey,
    [availableTemplates, design.template_key, defaultTemplateKey]
  )

  const selectedTemplate = useMemo(
    () => templates.find((tpl) => tpl.key === templateKey) || null,
    [templates, templateKey]
  )

  const onSave = () => {
    if (!requireFeature('custom_branding')) return
    // Persist the resolved key, not the possibly-blank stored one.
    save.mutate(
      { ...design, template_key: templateKey },
      {
        onSuccess: () => {
          setDirty(false)
          toast.success(t('walletDesign.saved'))
        },
        onError: (err) => {
          const { code, message } = normalizeError(err)
          toast.error(code === 'PLAN_LIMIT' ? t('walletDesign.locked') : message)
        },
      }
    )
  }

  const previewProps = {
    design,
    template: selectedTemplate,
    platformLogoUrl,
    platformLabel,
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

  const editable = (field) => Boolean(selectedTemplate?.editable?.includes(field))

  return (
    <div className="mt-6 rounded-card border border-line bg-surface p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-head text-lg font-bold text-tx">{t('walletDesign.title')}</h2>
        {/* Create mode has no card to save against yet — the card's own Save Draft /
            Publish persists this design straight after the card is created. */}
        {!controlled && (
          <Button onClick={onSave} loading={save.isPending} disabled={!dirty}>
            {t('walletDesign.save')}
          </Button>
        )}
      </div>

      {!branded && (
        <button
          type="button"
          onClick={() => requireFeature('custom_branding')}
          className="mb-4 w-full rounded-ctl bg-violet-bg px-4 py-2 text-left text-sm text-violet-d"
        >
          {t('walletDesign.upgradeNudge')}
        </button>
      )}

      {/* Template gallery — every card must pick a layout-locked template. */}
      <div className="mb-5">
        <h3 className="mb-2 text-sm font-semibold text-tx">{t('walletTemplates.choose')}</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {availableTemplates.map((tpl) => (
            <button
              key={tpl.key}
              type="button"
              disabled={!branded}
              onClick={() => set('template_key')(tpl.key)}
              className={`flex flex-col gap-1 rounded-ctl border p-2 text-left transition disabled:opacity-50 ${
                templateKey === tpl.key
                  ? 'border-primary ring-1 ring-primary'
                  : 'border-line hover:border-tx-3'
              }`}
            >
              <TemplateThumb
                tpl={tpl}
                colorBg={card?.color_bg || '#0E1B2A'}
                colorFg={card?.color_fg || '#FFFFFF'}
              />
              <span className="truncate text-xs font-semibold text-tx">{tpl.name}</span>
              <span className="text-[10px] text-tx-3">
                {t(`walletTemplates.visual_${tpl.bottom_visual}`)}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-2 rounded-ctl bg-paper px-3 py-2 text-xs text-tx-3">
          {t('walletTemplates.lockedNote')}
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Controls — only the selected template's editable variables. */}
        <fieldset disabled={!branded} className="flex flex-col gap-5 disabled:opacity-60">
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <ColorPicker
                label={t('walletDesign.labelColor')}
                value={design.label_color || card?.color_fg || '#FFFFFF'}
                onChange={set('label_color')}
              />
            </div>
            {editable('strip_bg_color') && (
              <ColorPicker
                label={t('walletDesign.stripBg')}
                value={design.strip_bg_color || card?.color_bg || '#0E1B2A'}
                onChange={set('strip_bg_color')}
              />
            )}
            {/* Stamp style — a built-in icon + its fill color, and how the stamps are
                arranged. The template says whether they apply (a stamps template
                does; an image/none one doesn't). */}
            {editable('stamp_icon') && (
              <div>
                <label className="mb-1 block text-sm text-tx-2">{t('designer.stampIcon')}</label>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => set('stamp_icon')('')}
                    className={`flex h-9 items-center rounded-ctl border px-2 text-xs ${
                      design.stamp_icon
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
                      aria-pressed={design.stamp_icon === key}
                      onClick={() => set('stamp_icon')(key)}
                      className={`flex h-9 w-9 items-center justify-center rounded-ctl border transition ${
                        design.stamp_icon === key
                          ? 'border-primary ring-1 ring-primary'
                          : 'border-line hover:border-tx-3'
                      }`}
                    >
                      <StampGlyph
                        icon={key}
                        filled
                        color={design.stamp_color || card?.color_fg || '#FFFFFF'}
                        size={20}
                      />
                    </button>
                  ))}
                </div>
              </div>
            )}
            {editable('stamp_color') && (
              <ColorPicker
                label={t('designer.stampColor')}
                value={design.stamp_color || card?.color_fg || '#FFFFFF'}
                onChange={set('stamp_color')}
              />
            )}
            {editable('stamp_layout') && (
              <div>
                <label className="mb-1 block text-sm text-tx-2">{t('designer.stampLayout')}</label>
                <div className="flex flex-wrap gap-1.5">
                  {STAMP_LAYOUTS.map((key) => (
                    <button
                      key={key || 'grid'}
                      type="button"
                      aria-pressed={(design.stamp_layout || '') === key}
                      onClick={() => set('stamp_layout')(key)}
                      className={`flex flex-col items-center gap-1 rounded-ctl border px-3 py-2 transition ${
                        (design.stamp_layout || '') === key
                          ? 'border-primary ring-1 ring-primary'
                          : 'border-line hover:border-tx-3'
                      }`}
                    >
                      <StampLayoutGlyph
                        layout={key}
                        color={design.stamp_color || card?.color_fg || '#FFFFFF'}
                      />
                      <span className="text-xs text-tx-2">
                        {t(`designer.stampLayout_${key || 'grid'}`)}
                      </span>
                    </button>
                  ))}
                </div>
                <p className="mt-1 text-xs text-tx-3">{t('designer.stampLayoutHint')}</p>
              </div>
            )}
            {editable('strip_empty_url') && (
              <div>
                <span className="mb-1 block text-xs text-tx-3">
                  {t('designer.stampUploadHint')}
                </span>
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
              </div>
            )}
            {editable('bottom_image_url') && (
              <div>
                <FileUpload
                  label={t('walletTemplates.bottomImage')}
                  onUploaded={set('bottom_image_url')}
                />
                <p className="mt-1 text-xs text-tx-3">{t('walletTemplates.bottomImageHint')}</p>
              </div>
            )}
            <p className="rounded-ctl bg-paper px-3 py-2 text-xs text-tx-3">
              {t('walletDesign.layoutNote')}
            </p>
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
