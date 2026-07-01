// Login (spec §14) — rhf + zod. On success: cache /me, redirect to ?next or /.
// UNAUTHENTICATED → inline "wrong email or password".
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { login, normalizeError } from '../../lib/api'
import AuthLayout from './AuthLayout'
import { Input } from '../../components/Field'
import { Checkbox } from '../../components/Toggle'
import Button from '../../components/Button'

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  remember: z.boolean().optional(),
})

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const qc = useQueryClient()

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { remember: true } })

  async function onSubmit(values) {
    try {
      await login(values.email, values.password)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate(decodeURIComponent(params.get('next') || '/'), { replace: true })
    } catch (err) {
      const { code, message } = normalizeError(err)
      setError('root', {
        message: code === 'UNAUTHENTICATED' ? t('login.error') : message,
      })
    }
  }

  return (
    <AuthLayout
      title={t('login.title')}
      footer={
        <span>
          {t('login.noAccount')} <Link to="/signup" className="text-amber-d font-semibold">{t('login.signup')}</Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input
          label={t('login.email')}
          type="email"
          autoComplete="email"
          error={errors.email && t('validation.email')}
          {...register('email')}
        />
        <Input
          label={t('login.password')}
          type="password"
          autoComplete="current-password"
          error={errors.password && t('validation.required')}
          {...register('password')}
        />
        <div className="flex items-center justify-between">
          <Checkbox
            checked={Boolean(watch('remember'))}
            onChange={(v) => setValue('remember', v)}
            label={t('login.remember')}
          />
          <Link to="/forgot" className="text-sm text-amber-d">
            {t('login.forgot')}
          </Link>
        </div>
        {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('login.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
