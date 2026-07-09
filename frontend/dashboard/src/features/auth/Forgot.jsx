// Forgot password (spec §14) — POST /auth/forgot. Always shows the same success
// message (never leaks whether the email exists).
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import api from '../../lib/api'
import AuthLayout from './AuthLayout'
import { Input } from '../../components/Field'
import Button from '../../components/Button'

const schema = z.object({ email: z.string().email() })

export default function Forgot() {
  const { t } = useTranslation()
  const [sent, setSent] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) })

  async function onSubmit(values) {
    try {
      await api.post('/auth/forgot', { email: values.email })
    } catch {
      // Intentionally ignore — the endpoint always 200s; never leak existence.
    }
    setSent(true)
  }

  const backToLogin = (
    <Link to="/login" className="font-semibold text-violet-d">
      {t('login.title')}
    </Link>
  )

  if (sent) {
    return (
      <AuthLayout title={t('forgot.sentTitle')} footer={backToLogin}>
        <p className="text-sm text-tx-2">{t('forgot.sentBody')}</p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout title={t('forgot.title')} subtitle={t('forgot.subtitle')} footer={backToLogin}>
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input
          label={t('login.email')}
          type="email"
          autoComplete="email"
          error={errors.email && t('validation.email')}
          {...register('email')}
        />
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('forgot.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
