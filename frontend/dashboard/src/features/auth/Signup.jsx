// Signup (spec §14) — rhf + zod. POST /auth/signup → save tokens → /onboarding.
// Duplicate email (409 CONFLICT) → inline field error. Consent (PDPL) required.
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { signup, normalizeError } from '../../lib/api'
import AuthLayout from './AuthLayout'
import { Input } from '../../components/Field'
import { Checkbox } from '../../components/Toggle'
import Button from '../../components/Button'

const schema = z.object({
  business_name: z.string().min(1),
  owner_name: z.string().min(1),
  email: z.string().email(),
  phone: z.string().min(6), // E.164-ish; backend validates strictly
  password: z.string().min(8),
  consent: z.literal(true),
})

export default function Signup() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()

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
      await signup(values)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate('/onboarding', { replace: true })
    } catch (err) {
      const { code, message, fields } = normalizeError(err)
      if (code === 'CONFLICT' || fields?.email) {
        setError('email', { message: t('signup.emailTaken') })
      } else {
        setError('root', { message })
      }
    }
  }

  return (
    <AuthLayout
      title={t('signup.title')}
      subtitle={t('signup.subtitle')}
      footer={
        <span>
          {t('signup.haveAccount')}{' '}
          <Link to="/login" className="font-semibold text-amber-d">
            {t('login.title')}
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input
          label={t('signup.businessName')}
          error={errors.business_name && t('validation.required')}
          {...register('business_name')}
        />
        <Input
          label={t('signup.ownerName')}
          error={errors.owner_name && t('validation.required')}
          {...register('owner_name')}
        />
        <Input
          label={t('login.email')}
          type="email"
          autoComplete="email"
          error={errors.email && (errors.email.message || t('validation.email'))}
          {...register('email')}
        />
        <Input
          label={t('signup.phone')}
          type="tel"
          dir="ltr"
          placeholder="+20…"
          error={errors.phone && t('validation.required')}
          {...register('phone')}
        />
        <Input
          label={t('login.password')}
          type="password"
          autoComplete="new-password"
          error={errors.password && t('validation.min8')}
          {...register('password')}
        />
        <Checkbox
          checked={Boolean(watch('consent'))}
          onChange={(v) => setValue('consent', v, { shouldValidate: true })}
          label={t('signup.consent')}
        />
        {errors.consent && <p className="text-xs text-danger">{t('signup.consentRequired')}</p>}
        {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('signup.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
