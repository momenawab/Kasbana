import { useTranslation } from 'react-i18next'

/** Phase-1 placeholder for not-yet-built feature screens. */
export default function Placeholder({ title }) {
  const { t } = useTranslation()
  return (
    <div className="rounded-card border border-line bg-white p-8 shadow-bold">
      <h1 className="font-head text-2xl font-bold text-ink">{title}</h1>
      <p className="mt-2 text-tx-2">{t('common.comingSoon')}</p>
    </div>
  )
}
