// Reset password (spec §14) — /reset/:token. password + confirm → POST
// /auth/reset → /login. Invalid/expired token (410 TOKEN_EXPIRED) → clear msg.
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../../lib/api'
import AuthLayout from './AuthLayout'
import { Input } from '../../components/Field'
import Button from '../../components/Button'
import { useToast } from '../../hooks/useToast'

const schema = z
  .object({
    password: z.string().min(8),
    confirm: z.string().min(8),
  })
  .refine((v) => v.password === v.confirm, { path: ['confirm'], message: 'mismatch' })

export default function Reset() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { token } = useParams()
  const toast = useToast()
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) })

  async function onSubmit(values) {
    try {
      await api.post('/auth/reset', { token, password: values.password })
      toast.success(t('reset.success'))
      navigate('/login', { replace: true })
    } catch (err) {
      const { code, message } = normalizeError(err)
      setError('root', {
        message: code === 'TOKEN_EXPIRED' ? t('reset.expired') : message,
      })
    }
  }

  return (
    <AuthLayout
      title={t('reset.title')}
      footer={
        <Link to="/login" className="font-semibold text-violet-d">
          {t('login.title')}
        </Link>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input
          label={t('reset.newPassword')}
          type="password"
          autoComplete="new-password"
          error={errors.password && t('validation.min8')}
          {...register('password')}
        />
        <Input
          label={t('reset.confirmPassword')}
          type="password"
          autoComplete="new-password"
          error={errors.confirm && t('reset.mismatch')}
          {...register('confirm')}
        />
        {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('reset.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
