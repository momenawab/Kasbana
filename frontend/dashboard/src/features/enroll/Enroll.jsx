// Public customer enrollment page (no auth) — opened by scanning a card's QR.
// GET branding+theme → themed form (fields per the merchant's config) → POST →
// "Add to Google Wallet". Apple shown later once an Apple account exists; for
// now every platform gets the Google button (apple_pass_url is null).
import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import api, { normalizeError } from '../../lib/api'
import { setLang } from '../../lib/i18n'
import { useTranslation } from 'react-i18next'
import { Input } from '../../components/Field'
import { Checkbox } from '../../components/Toggle'
import Button from '../../components/Button'
import WalletPreview from '../../components/WalletPreview'
import Skeleton from '../../components/Skeleton'

// Official "Add to Google Wallet" button (self-hosted in public/).
const GOOGLE_BADGE = '/add-to-google-wallet.png'

// Build the validation schema from the merchant's field config: phone + consent
// are always required; name/email/birthday are optional unless shown+required.
function buildSchema(fc) {
  const optional = z.string().optional().or(z.literal(''))
  const req = (base) => base
  return z.object({
    customer_phone: z.string().min(6),
    customer_name: fc?.name?.show && fc?.name?.required ? z.string().min(1) : optional,
    customer_email:
      fc?.email?.show && fc?.email?.required
        ? z.string().email()
        : z.string().email().optional().or(z.literal('')),
    birthday: fc?.birthday?.show && fc?.birthday?.required ? z.string().min(1) : optional,
    consent: req(z.literal(true)),
  })
}

export default function Enroll() {
  const { token } = useParams()
  const [searchParams] = useSearchParams()
  const ref = searchParams.get('ref') // referrer's customer_card id, if shared
  const { t, i18n } = useTranslation()
  const [info, setInfo] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState(null) // { google_save_url, apple_pass_url }

  useEffect(() => {
    let active = true
    api
      .get(`/enroll/${token}`)
      .then(({ data }) => active && setInfo(data))
      .catch((err) => {
        if (!active) return
        const { code } = normalizeError(err)
        setLoadError(code === 'TOKEN_EXPIRED' ? t('enroll.expired') : t('enroll.invalid'))
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [token, t])

  const toggleLang = () => setLang(i18n.language === 'ar' ? 'en' : 'ar')

  if (loading) {
    return (
      <Centered>
        <Skeleton h={120} rounded="card" className="mb-3" />
        <Skeleton h={200} rounded="card" />
      </Centered>
    )
  }

  if (loadError) {
    return (
      <Centered>
        <p className="text-center text-danger">{loadError}</p>
      </Centered>
    )
  }

  const theme = info.theme || {}
  const preview = (
    <WalletPreview
      platform="GOOGLE"
      logoUrl={info.logo_url}
      colorBg={info.color_bg || '#0E1B2A'}
      colorFg={info.color_fg || '#FFFFFF'}
      merchantName={info.merchant_name}
      programName={info.card_name}
      rewardTitle={info.reward_title}
      stampsRequired={info.stamps_required}
      stampCount={0}
    />
  )

  // Success: show the Add-to-Google-Wallet button.
  if (result) {
    return (
      <Centered bg={theme.bg_color}>
        <div className="flex flex-col items-center gap-5 text-center">
          {preview}
          <div>
            <h2 className="font-head text-xl font-bold text-ink">{t('enroll.successTitle')}</h2>
            <p className="mt-1 text-sm text-tx-2">{t('enroll.successBody')}</p>
          </div>
          {result.google_save_url ? (
            <a
              href={result.google_save_url}
              target="_blank"
              rel="noreferrer"
              aria-label={t('enroll.addGoogle')}
            >
              <img src={GOOGLE_BADGE} alt={t('enroll.addGoogle')} className="h-12" />
            </a>
          ) : (
            <p className="text-sm text-tx-3">{t('enroll.noWallet')}</p>
          )}
          {/* Apple button intentionally omitted until an Apple account exists. */}
          {result.referral_url && <ReferShare url={result.referral_url} />}
        </div>
      </Centered>
    )
  }

  return (
    <Centered bg={theme.bg_color}>
      <div className="mb-3 flex justify-end">
        <button onClick={toggleLang} className="text-sm text-tx-2 underline">
          {i18n.language === 'ar' ? 'English' : 'العربية'}
        </button>
      </div>
      {theme.cover_image_url && (
        <img
          src={theme.cover_image_url}
          alt=""
          className="mb-4 h-28 w-full rounded-card object-cover"
        />
      )}
      <div className="mb-5 flex justify-center">{preview}</div>
      <h1 className="text-center font-head text-2xl font-bold text-ink">
        {info.headline || t('enroll.title', { merchant: info.merchant_name })}
      </h1>
      <p className="mb-4 text-center text-sm text-tx-2">
        {theme.welcome_body || info.tagline || t('enroll.subtitle', { reward: info.reward_title })}
      </p>

      <EnrollForm info={info} token={token} refId={ref} onEnrolled={setResult} />

      {info.show_powered_by && (
        <p className="mt-4 text-center text-xs text-tx-3">{t('enroll.poweredBy')}</p>
      )}
    </Centered>
  )
}

function EnrollForm({ info, token, refId, onEnrolled }) {
  const { t } = useTranslation()
  const theme = useMemo(() => info.theme || {}, [info])
  const fc = theme.fields_config || {}
  const schema = useMemo(() => buildSchema(theme.fields_config || {}), [theme])
  const accent = theme.accent_color || info.color_bg || '#0E1B2A'
  const btnText = theme.button_text_color || info.color_fg || '#FFFFFF'

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { consent: false } })

  async function onSubmit(values) {
    try {
      const { data } = await api.post(`/enroll/${token}`, {
        customer_name: values.customer_name || '',
        customer_phone: values.customer_phone,
        customer_email: values.customer_email || '',
        birthday: values.birthday || null,
        consent: true,
        ref: refId || null,
      })
      onEnrolled(data)
    } catch (err) {
      const { code, message } = normalizeError(err)
      if (code === 'ALREADY_ENROLLED') setError('customer_phone', { message: t('enroll.already') })
      else setError('root', { message })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
      {fc.name?.show && (
        <Input
          label={t('enroll.name')}
          required={fc.name?.required}
          {...register('customer_name')}
        />
      )}
      <Input
        label={t('enroll.phone')}
        type="tel"
        dir="ltr"
        required
        placeholder="+20…"
        error={errors.customer_phone && t('enroll.phoneInvalid')}
        {...register('customer_phone')}
      />
      {fc.email?.show && (
        <Input
          label={t('enroll.email')}
          type="email"
          dir="ltr"
          required={fc.email?.required}
          error={errors.customer_email && t('validation.email')}
          {...register('customer_email')}
        />
      )}
      {fc.birthday?.show && (
        <Input
          label={t('enroll.birthday')}
          type="date"
          required={fc.birthday?.required}
          {...register('birthday')}
        />
      )}
      <Checkbox
        checked={Boolean(watch('consent'))}
        onChange={(v) => setValue('consent', v, { shouldValidate: true })}
        label={t('enroll.consent')}
      />
      {(theme.terms_url || theme.privacy_url) && (
        <div className="flex flex-wrap gap-x-3 text-xs text-tx-3">
          {theme.terms_url && (
            <a href={theme.terms_url} target="_blank" rel="noreferrer" className="underline">
              {t('enroll.terms')}
            </a>
          )}
          {theme.privacy_url && (
            <a href={theme.privacy_url} target="_blank" rel="noreferrer" className="underline">
              {t('enroll.privacy')}
            </a>
          )}
        </div>
      )}
      {errors.consent && <p className="text-xs text-danger">{t('enroll.consentRequired')}</p>}
      {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
      <Button
        type="submit"
        loading={isSubmitting}
        className="w-full"
        style={{ background: accent, color: btnText }}
      >
        {t('enroll.submit')}
      </Button>
    </form>
  )
}

function Centered({ children, bg }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <div
        className="w-full max-w-sm rounded-card bg-white p-6 shadow-bold"
        style={bg ? { background: bg } : undefined}
      >
        {children}
      </div>
    </div>
  )
}

// "Refer a friend" — share your link; both earn a bonus stamp when they join.
function ReferShare({ url }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const share = async () => {
    try {
      if (navigator.share) await navigator.share({ url })
      else {
        await navigator.clipboard.writeText(url)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }
    } catch {
      /* user cancelled the share sheet — ignore */
    }
  }
  return (
    <div className="mt-2 w-full rounded-ctl border border-line bg-paper p-3 text-center">
      <p className="mb-2 text-sm font-semibold text-ink">{t('enroll.referTitle')}</p>
      <p className="mb-3 text-xs text-tx-2">{t('enroll.referBody')}</p>
      <Button size="sm" onClick={share} className="w-full">
        {copied ? t('qr.copied') : t('enroll.referShare')}
      </Button>
    </div>
  )
}
