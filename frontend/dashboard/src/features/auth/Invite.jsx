// Invite accept (spec §14) — GET /auth/invite/:token shows merchant+role+email,
// then set password → POST /auth/invite/:token → logged in → /. Expired (410)
// shows a clear message.
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import api, { acceptInvite, normalizeError } from '../../lib/api'
import AuthLayout from './AuthLayout'
import { Input } from '../../components/Field'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'

const schema = z.object({ password: z.string().min(8) })

export default function Invite() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { token } = useParams()
  const qc = useQueryClient()

  const [info, setInfo] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema) })

  useEffect(() => {
    let active = true
    api
      .get(`/auth/invite/${token}`)
      .then(({ data }) => active && setInfo(data))
      .catch((err) => {
        if (!active) return
        const { code } = normalizeError(err)
        setLoadError(code === 'TOKEN_EXPIRED' ? t('invite.expired') : t('invite.invalid'))
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [token, t])

  async function onSubmit(values) {
    try {
      await acceptInvite(token, values.password)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate('/', { replace: true })
    } catch (err) {
      const { code, message } = normalizeError(err)
      setError('root', { message: code === 'TOKEN_EXPIRED' ? t('invite.expired') : message })
    }
  }

  const backToLogin = (
    <Link to="/login" className="font-semibold text-amber-d">
      {t('login.title')}
    </Link>
  )

  if (loading) {
    return (
      <AuthLayout title={t('invite.title')}>
        <Skeleton h={20} className="mb-2" />
        <Skeleton h={40} />
      </AuthLayout>
    )
  }

  if (loadError) {
    return (
      <AuthLayout title={t('invite.title')} footer={backToLogin}>
        <p className="text-sm text-danger">{loadError}</p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout
      title={t('invite.title')}
      subtitle={t('invite.subtitle', {
        merchant: info.merchant_name,
        role: info.role,
      })}
      footer={backToLogin}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
        <Input label={t('login.email')} value={info.email} disabled readOnly />
        <Input
          label={t('invite.setPassword')}
          type="password"
          autoComplete="new-password"
          error={errors.password && t('validation.min8')}
          {...register('password')}
        />
        {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
        <Button type="submit" loading={isSubmitting} className="w-full">
          {t('invite.submit')}
        </Button>
      </form>
    </AuthLayout>
  )
}
