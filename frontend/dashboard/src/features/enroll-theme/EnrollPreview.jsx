// A non-interactive mock of the public join page, driven by the editor's live
// form state (finalize Phase 2). Colors are already "effective" (theme override
// falling back to the card/merchant brand color) when passed in.
import { useTranslation } from 'react-i18next'
import QrBlock from '../../components/QrBlock'

function PreviewField({ label, required }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-tx-2">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      <div className="h-8 w-full rounded-ctl border border-line bg-white" />
    </label>
  )
}

export default function EnrollPreview({
  theme,
  merchantName,
  programName,
  rewardTitle,
  logoUrl,
  joinUrl = 'https://app.stampn.net/enroll/preview',
}) {
  const { t } = useTranslation()
  const accent = theme.accent_color || '#0E1B2A'
  const btnText = theme.button_text_color || '#FFFFFF'
  const pageBg = theme.bg_color || '#FFFFFF'
  const fc = theme.fields_config || {}
  const qr = theme.qr_style || {}
  const showPoweredBy = !theme.hide_powered_by

  return (
    <div className="rounded-card border border-line bg-paper p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-tx-3">
        {t('enrollTheme.preview')}
      </p>
      <div
        className="mx-auto w-full max-w-xs overflow-hidden rounded-card shadow-bold"
        style={{ background: pageBg }}
      >
        {theme.cover_image_url && (
          <img src={theme.cover_image_url} alt="" className="h-24 w-full object-cover" />
        )}
        <div className="p-5">
          <div className="mb-3 flex items-center gap-2">
            {logoUrl ? (
              <img src={logoUrl} alt="" className="h-9 w-9 rounded-full object-cover" />
            ) : (
              <span
                className="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
                style={{ background: accent }}
              >
                {merchantName.slice(0, 1)}
              </span>
            )}
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink">{merchantName}</div>
              <div className="truncate text-xs text-tx-3">{programName}</div>
            </div>
          </div>

          <h3 className="font-head text-lg font-bold text-ink">
            {t('enroll.title', { merchant: merchantName })}
          </h3>
          <p className="mb-4 mt-1 text-xs text-tx-2">
            {theme.welcome_body || t('enroll.subtitle', { reward: rewardTitle })}
          </p>

          <div className="flex flex-col gap-2">
            {fc.name?.show && (
              <PreviewField label={t('enroll.name')} required={fc.name?.required} />
            )}
            <PreviewField label={t('enroll.phone')} required />
            {fc.email?.show && (
              <PreviewField label={t('enroll.email')} required={fc.email?.required} />
            )}
            {fc.birthday?.show && (
              <PreviewField label={t('enroll.birthday')} required={fc.birthday?.required} />
            )}
          </div>

          <div
            className="mt-4 flex h-9 items-center justify-center rounded-ctl text-sm font-semibold"
            style={{ background: accent, color: btnText }}
          >
            {t('enroll.submit')}
          </div>

          {(theme.terms_url || theme.privacy_url) && (
            <div className="mt-2 flex justify-center gap-3 text-[10px] text-tx-3 underline">
              {theme.terms_url && <span>{t('enroll.terms')}</span>}
              {theme.privacy_url && <span>{t('enroll.privacy')}</span>}
            </div>
          )}

          {showPoweredBy && (
            <p className="mt-3 text-center text-[10px] text-tx-3">{t('enroll.poweredBy')}</p>
          )}
        </div>
      </div>

      {/* QR preview — colors live; shape (dots/rounded) applies on the saved QR. */}
      <div className="mt-4 flex justify-center">
        <QrBlock
          value={joinUrl}
          size={140}
          fgColor={qr.fg_color || '#0E1B2A'}
          bgColor={qr.bg_color || '#FFFFFF'}
          downloadName="enroll-qr-preview"
        />
      </div>
    </div>
  )
}
