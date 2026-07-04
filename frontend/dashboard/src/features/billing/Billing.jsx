// Billing (spec §14) — current plan + trial countdown, plan matrix, subscribe →
// checkout_url redirect, usage bars vs limits, invoices, cancel. All 1.7 backend
// (graceful: falls back to /me entitlements for plan/usage until promotion).
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import Button from '../../components/Button'
import Badge from '../../components/Badge'
import Table from '../../components/Table'
import { arDigits, daysUntil, fmtDate, money } from '../../lib/format'

const PLANS = ['starter', 'growth', 'chain']

function UsageBar({ label, used, max, lang }) {
  const pct = max == null ? 0 : Math.min(100, Math.round((used / max) * 100))
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span className="text-tx-2">{label}</span>
        <span className="font-num text-tx">
          {arDigits(used, lang)} / {max == null ? '∞' : arDigits(max, lang)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-paper">
        <div className="h-full bg-amber" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function Billing() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const { merchant } = useAuth()
  const { entitlements } = usePlan()
  const toast = useToast()
  const qc = useQueryClient()

  const { data: billing } = useQuery({
    queryKey: ['billing'],
    queryFn: async () => {
      try {
        return (await api.get('/billing')).data
      } catch {
        return null
      }
    },
  })
  const { data: invoices = [] } = useQuery({
    queryKey: ['billing', 'invoices'],
    queryFn: async () => {
      try {
        return (await api.get('/billing/invoices')).data.results ?? []
      } catch {
        return []
      }
    },
  })

  const plan = billing?.plan || merchant?.plan || entitlements?.plan
  const trialEnds = billing?.trial_ends_at || merchant?.trial_ends_at
  const cancelsOn = billing?.cancels_on
  const usage = billing?.usage || entitlements?.usage || {}
  const limits = entitlements?.limits || {}

  const subscribe = useMutation({
    mutationFn: async (target) => (await api.post('/billing/subscribe', { plan: target })).data,
    onSuccess: (data) => {
      if (data.checkout_url) window.location.assign(data.checkout_url)
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  const cancel = useMutation({
    mutationFn: async (reason) => (await api.post('/billing/cancel', { reason })).data,
    onSuccess: (data) => {
      toast.success(
        data?.cancels_on
          ? t('billing.canceledUntil', { date: fmtDate(data.cancels_on, lang) })
          : t('billing.canceled')
      )
      qc.invalidateQueries({ queryKey: ['billing'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  function doCancel() {
    const reason = window.prompt(t('billing.cancelReason'))
    if (reason != null) cancel.mutate(reason)
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-head text-2xl font-bold text-ink">{t('billing.title')}</h1>

      {/* Current plan + trial */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-white p-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-tx-2">{t('billing.currentPlan')}:</span>
            <Badge tone="amber">{t(`billing.plan.${plan}`, plan)}</Badge>
          </div>
          {plan === 'trial' && trialEnds && (
            <p className="mt-1 text-sm text-tx-3">
              {t('billing.trialLeft', { count: arDigits(daysUntil(trialEnds), lang) })}
            </p>
          )}
          {cancelsOn && (
            <p className="mt-1 text-sm text-amber-d">
              {t('billing.cancelsOn', { date: fmtDate(cancelsOn, lang) })}
            </p>
          )}
        </div>
        {plan !== 'chain' && !cancelsOn && (
          <Button variant="ghost" onClick={doCancel} loading={cancel.isPending}>
            {t('billing.cancel')}
          </Button>
        )}
      </div>

      {/* Usage bars */}
      <div className="grid gap-4 rounded-card border border-line bg-white p-5 sm:grid-cols-2">
        <UsageBar
          label={t('overview.enrollments')}
          used={usage.customers ?? 0}
          max={limits.max_customers}
          lang={lang}
        />
        <UsageBar
          label={t('nav.cards')}
          used={usage.cards ?? 0}
          max={limits.max_cards}
          lang={lang}
        />
        <UsageBar
          label={t('nav.locations')}
          used={usage.locations ?? 0}
          max={limits.max_locations}
          lang={lang}
        />
        <UsageBar
          label={t('nav.team')}
          used={usage.staff ?? 0}
          max={limits.max_staff}
          lang={lang}
        />
      </div>

      {/* Plan matrix */}
      <div className="grid gap-4 sm:grid-cols-3">
        {PLANS.map((p) => (
          <div
            key={p}
            className={`rounded-card border p-5 ${plan === p ? 'border-amber bg-amber-bg' : 'border-line bg-white'}`}
          >
            <h3 className="font-head text-lg font-bold text-ink">{t(`billing.plan.${p}`)}</h3>
            <Button
              className="mt-4 w-full"
              variant={plan === p ? 'ghost' : 'primary'}
              disabled={plan === p}
              loading={subscribe.isPending}
              onClick={() => subscribe.mutate(p)}
            >
              {plan === p ? t('billing.current') : t('billing.choose')}
            </Button>
          </div>
        ))}
      </div>

      {/* Invoices */}
      <div>
        <h2 className="mb-3 font-head font-semibold text-ink">{t('billing.invoices')}</h2>
        <Table
          columns={[
            { key: 'date', label: t('billing.date') },
            {
              key: 'amount_egp',
              label: t('billing.amount'),
              render: (r) => money(r.amount_egp, lang),
            },
            {
              key: 'status',
              label: t('billing.statusCol'),
              render: (r) => (
                <Badge tone={r.status === 'paid' ? 'success' : 'amber'}>{r.status}</Badge>
              ),
            },
            {
              key: 'pdf_url',
              label: '',
              render: (r) =>
                r.pdf_url ? (
                  <a href={r.pdf_url} className="text-amber-d" target="_blank" rel="noreferrer">
                    PDF
                  </a>
                ) : null,
            },
          ]}
          rows={invoices}
          emptyState={
            <div className="rounded-card border border-line bg-white p-6 text-center text-tx-3">
              {t('billing.noInvoices')}
            </div>
          }
        />
      </div>
    </div>
  )
}
