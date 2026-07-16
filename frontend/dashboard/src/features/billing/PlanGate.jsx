// Signup gate (Paymob plan §11.5) — what a merchant sees before the dashboard
// exists for them: welcome → pick a plan → add a card.
//
// The trial is card-upfront, so there is nothing to see until a card is on
// file: adding one runs a 1 EGP verification through Paymob's checkout, which
// both proves the card is real and links the subscription that auto-charges at
// day 14. Rendered by Shell whenever /me reports needs_card, so it replaces the
// app rather than sitting inside it — every other route is locked anyway.
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import Button from '../../components/Button'
import { money } from '../../lib/format'

const FEATURES = ['cards', 'stamps', 'customers', 'analytics']

export default function PlanGate() {
  const { t } = useTranslation()
  const { i18n } = useTranslation()
  const lang = i18n.language
  const { merchant } = useAuth()
  const toast = useToast()

  const [step, setStep] = useState('intro')
  const [interval, setInterval] = useState('monthly')
  const [selected, setSelected] = useState(null)

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ['billing', 'plans'],
    // Prices are admin-editable without a deploy, so they are served, never
    // hardcoded here — a stale copy would advertise a price checkout won't take.
    queryFn: async () => (await api.get('/billing/plans')).data,
  })

  const start = useMutation({
    mutationFn: async (plan) =>
      (await api.post('/billing/subscribe', { plan, interval })).data,
    onSuccess: (data) => {
      // Leaves the SPA for Paymob's hosted checkout; we come back via the
      // intention's redirection_url once 3DS completes.
      if (data.checkout_url) window.location.assign(data.checkout_url)
      else toast.error(t('gate.noCheckout'))
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  if (step === 'intro') {
    return (
      <Gate title={t('gate.welcome', { name: merchant?.name || '' })}>
        <p className="text-tx-2">{t('gate.introBody')}</p>
        <ul className="my-6 flex flex-col gap-3">
          {FEATURES.map((f) => (
            <li key={f} className="flex items-start gap-3">
              <span aria-hidden="true" className="mt-1 text-violet">
                ●
              </span>
              <div>
                <p className="font-semibold text-tx">{t(`gate.feature.${f}.title`)}</p>
                <p className="text-sm text-tx-2">{t(`gate.feature.${f}.body`)}</p>
              </div>
            </li>
          ))}
        </ul>
        <Button className="w-full" onClick={() => setStep('plan')}>
          {t('gate.introCta')}
        </Button>
      </Gate>
    )
  }

  return (
    <Gate title={t('gate.planTitle')}>
      <p className="text-tx-2">{t('gate.planBody')}</p>

      <div
        role="group"
        aria-label={t('gate.intervalLabel')}
        className="my-5 inline-flex rounded-ctl border border-line bg-paper p-1"
      >
        {['monthly', 'annual'].map((opt) => (
          <button
            key={opt}
            type="button"
            aria-pressed={interval === opt}
            onClick={() => setInterval(opt)}
            className={`rounded-ctl px-4 py-1.5 text-sm font-semibold ${
              interval === opt ? 'bg-violet text-white' : 'text-tx-2'
            }`}
          >
            {t(`gate.${opt}`)}
            {opt === 'annual' && (
              <span className="ms-2 text-xs opacity-80">{t('gate.annualSaving')}</span>
            )}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-tx-3">{t('common.loading')}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          {plans.map((p) => {
            const price = interval === 'annual' ? p.price_egp_annual : p.price_egp
            const isSelected = selected === p.key
            return (
              <button
                key={p.key}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setSelected(p.key)}
                className={`rounded-card border p-4 text-start ${
                  isSelected ? 'border-violet bg-violet-bg' : 'border-line bg-surface'
                }`}
              >
                <h3 className="font-head font-bold text-tx">{p.name}</h3>
                <p className="mt-2 font-num text-lg text-tx">{money(price, lang)}</p>
                <p className="text-xs text-tx-3">
                  {t(interval === 'annual' ? 'gate.perYear' : 'gate.perMonth')}
                </p>
              </button>
            )
          })}
        </div>
      )}

      <p className="mt-5 text-sm text-tx-2">{t('gate.cardExplainer')}</p>

      <Button
        className="mt-3 w-full"
        disabled={!selected}
        loading={start.isPending}
        onClick={() => start.mutate(selected)}
      >
        {t('gate.startTrial')}
      </Button>
      <button
        type="button"
        onClick={() => setStep('intro')}
        className="mt-3 w-full text-sm text-tx-2 hover:text-tx"
      >
        {t('gate.back')}
      </button>
    </Gate>
  )
}

function Gate({ title, children }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper p-4">
      <div className="w-full max-w-2xl rounded-card border border-line bg-surface p-6 sm:p-8">
        <h1 className="font-head text-2xl font-bold text-tx">{title}</h1>
        <div className="mt-3">{children}</div>
      </div>
    </div>
  )
}
