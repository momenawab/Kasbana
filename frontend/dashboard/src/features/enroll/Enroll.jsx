// Public customer enrollment page (no auth) — opened by scanning a card's QR.
// GET branding → form (name/phone/email/birthday + PDPL consent) → POST →
// "Add to Google Wallet". Apple shown later once an Apple account exists; for
// now every platform gets the Google button (apple_pass_url is null).
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
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

const schema = z.object({
  customer_name: z.string().optional(),
  customer_phone: z.string().min(6),
  customer_email: z.string().email().optional().or(z.literal('')),
  birthday: z.string().optional().or(z.literal('')),
  consent: z.literal(true),
})

// Official "Add to Google Wallet" button (self-hosted in public/).
const GOOGLE_BADGE = '/add-to-google-wallet.png'

export default function Enroll() {
  const { token } = useParams()
  const { t, i18n } = useTranslation()
  const [info, setInfo] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [result, setResult] = useState(null) // { google_save_url, apple_pass_url }

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { consent: false } })

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

  async function onSubmit(values) {
    try {
      const { data } = await api.post(`/enroll/${token}`, {
        customer_name: values.customer_name || '',
        customer_phone: values.customer_phone,
        customer_email: values.customer_email || '',
        birthday: values.birthday || null,
        consent: true,
      })
      setResult(data)
    } catch (err) {
      const { code, message } = normalizeError(err)
      if (code === 'ALREADY_ENROLLED') setError('customer_phone', { message: t('enroll.already') })
      else setError('root', { message })
    }
  }

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
      <Centered>
        <div className="flex flex-col items-center gap-5 text-center">
          {preview}
          <div>
            <h2 className="font-head text-xl font-bold text-ink">{t('enroll.successTitle')}</h2>
            <p className="mt-1 text-sm text-tx-2">{t('enroll.successBody')}</p>
          </div>
          {result.google_save_url ? (
            <a href={result.google_save_url} target="_blank" rel="noreferrer" aria-label={t('enroll.addGoogle')}>
              <img src={GOOGLE_BADGE} alt={t('enroll.addGoogle')} className="h-12" />
            </a>
          ) : (
            <p className="text-sm text-tx-3">{t('enroll.noWallet')}</p>
          )}
          {/* Apple button intentionally omitted until an Apple account exists. */}
        </div>
      </Centered>
    )
  }

  return (
    <Centered>
      <div className="mb-3 flex justify-end">
        <button onClick={toggleLang} className="text-sm text-tx-2 underline">
          {i18n.language === 'ar' ? 'English' : 'العربية'}
        </button>
      </div>
      <div className="mb-5 flex justify-center">{preview}</div>
      <h1 className="text-center font-head text-2xl font-bold text-ink">
        {info.headline || t('enroll.title', { merchant: info.merchant_name })}
      </h1>
      <p className="mb-4 text-center text-sm text-tx-2">
        {info.tagline || t('enroll.subtitle', { reward: info.reward_title })}
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input label={t('enroll.name')} {...register('customer_name')} />
        <Input
          label={t('enroll.phone')}
          type="tel"
          dir="ltr"
          placeholder="+20…"
          error={errors.customer_phone && t('enroll.phoneInvalid')}
          {...register('customer_phone')}
        />
        <Input
          label={t('enroll.email')}
          type="email"
          dir="ltr"
          error={errors.customer_email && t('validation.email')}
          {...register('customer_email')}
        />
        <Input label={t('enroll.birthday')} type="date" {...register('birthday')} />
        <Checkbox
          checked={Boolean(watch('consent'))}
          onChange={(v) => setValue('consent', v, { shouldValidate: true })}
          label={t('enroll.consent')}
        />
        {errors.consent && <p className="text-xs text-danger">{t('enroll.consentRequired')}</p>}
        {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('enroll.submit')}
        </Button>
      </form>
      {info.show_powered_by && (
        <p className="mt-4 text-center text-xs text-tx-3">{t('enroll.poweredBy')}</p>
      )}
    </Centered>
  )
}

function Centered({ children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <div className="w-full max-w-sm rounded-card bg-white p-6 shadow-bold">{children}</div>
    </div>
  )
}
