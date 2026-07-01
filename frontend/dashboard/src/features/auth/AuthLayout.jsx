// Shared centered card shell for the auth screens (Login/Signup/Forgot/Reset/Invite).
import { useTranslation } from 'react-i18next'

export default function AuthLayout({ title, subtitle, children, footer }) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center font-head text-2xl font-bold text-ink">
          {t('app.name')}
        </div>
        <div className="rounded-card bg-white p-6 shadow-bold">
          <h1 className="font-head text-xl font-bold text-ink">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-tx-2">{subtitle}</p>}
          <div className="mt-4">{children}</div>
        </div>
        {footer && <div className="mt-4 text-center text-sm text-tx-2">{footer}</div>}
      </div>
    </div>
  )
}
