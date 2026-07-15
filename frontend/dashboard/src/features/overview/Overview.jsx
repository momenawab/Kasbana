// Overview — data home: brand KPI cards, a signature dark trend card with a
// metric switch, a live activity feed, and quick actions. /analytics/summary
// is live (1.3); timeseries + activity are 1.6 (graceful fallback to empty).
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Users,
  Stamp,
  Gift,
  UserPlus,
  QrCode,
  MessageSquare,
  ChevronRight,
  Activity,
} from 'lucide-react'
import api from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import KpiTile from '../../components/KpiTile'
import { ChartLine } from '../../components/Charts'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import EmptyState from '../../components/EmptyState'
import { fromNow } from '../../lib/format'

const METRICS = ['joins', 'stamps', 'redemptions']

const QUICK_ACTIONS = [
  { to: '/cards', key: 'qaShareQr', Icon: QrCode, accent: 'bg-violet/10 text-violet-d' },
  { to: '/campaigns/new', key: 'qaCampaign', Icon: MessageSquare, accent: 'bg-fuchsia/10 text-fuchsia-d' },
  { to: '/customers', key: 'qaCustomers', Icon: Users, accent: 'bg-teal/10 text-teal' },
]

function useSummary() {
  return useQuery({
    queryKey: ['analytics', 'summary'],
    queryFn: async () => (await api.get('/analytics/summary')).data,
  })
}

function useTimeseries(metric) {
  return useQuery({
    queryKey: ['analytics', 'timeseries', metric],
    queryFn: async () => {
      try {
        return (await api.get(`/analytics/timeseries?metric=${metric}`)).data.points ?? []
      } catch {
        return [] // 1.6 endpoint — empty until backend prod promotion
      }
    },
  })
}

function useActivity() {
  return useQuery({
    queryKey: ['activity'],
    queryFn: async () => {
      try {
        return (await api.get('/activity?limit=8')).data.results ?? []
      } catch {
        return []
      }
    },
  })
}

export default function Overview() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { merchant } = useAuth()
  const [metric, setMetric] = useState('joins')

  const { data: summary, isLoading } = useSummary()
  const { data: points = [] } = useTimeseries(metric)
  const { data: activity = [] } = useActivity()

  const isFresh = !isLoading && summary && (summary.enrollments ?? 0) === 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-head text-2xl font-bold text-tx md:text-3xl">
          {t('overview.greeting', { name: merchant?.name || '' })}
        </h1>
        <p className="mt-1 text-sm text-tx-2">{t('overview.subtitle')}</p>
      </div>

      {/* KPI tiles */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} h={132} rounded="card" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiTile label={t('overview.enrollments')} value={summary?.enrollments ?? 0} icon={Users} tone="violet" />
          <KpiTile label={t('overview.activeCards')} value={summary?.active_cards ?? 0} icon={Stamp} tone="teal" />
          <KpiTile label={t('overview.redemptions')} value={summary?.redemptions ?? 0} icon={Gift} tone="fuchsia" />
          <KpiTile
            label={t('overview.repeatRate')}
            value={`${Math.round((summary?.repeat_rate ?? 0) * 100)}%`}
            icon={UserPlus}
            tone="slate"
          />
        </div>
      )}

      {isFresh ? (
        <EmptyState
          icon={QrCode}
          title={t('overview.freshTitle')}
          body={t('overview.freshBody')}
          action={<Button onClick={() => navigate('/cards')}>{t('overview.shareQr')}</Button>}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Signature dark trend card — stays dark in both themes (brand accent). */}
          <div className="relative overflow-hidden rounded-card border border-white/10 bg-slate p-5 text-white shadow-bold lg:col-span-2">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -end-16 -top-16 h-48 w-48 rounded-full bg-violet/25 blur-3xl"
            />
            <div className="relative mb-4 flex items-center justify-between gap-3">
              <h2 className="font-head font-semibold">{t('overview.trend')}</h2>
              <div className="flex gap-1 rounded-full bg-white/10 p-1">
                {METRICS.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMetric(m)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                      metric === m ? 'bg-violet text-white shadow-pop' : 'text-white/60 hover:text-white'
                    }`}
                  >
                    {t(`overview.metric.${m}`)}
                  </button>
                ))}
              </div>
            </div>
            {points.length ? (
              <ChartLine data={points} />
            ) : (
              <p className="py-12 text-center text-sm text-white/50">{t('overview.noChart')}</p>
            )}
          </div>

          {/* Activity feed */}
          <div className="theme-t rounded-card border border-line bg-surface p-5 shadow-card">
            <h2 className="mb-4 flex items-center gap-2 font-head font-semibold text-tx">
              <Activity size={16} className="text-violet-d" />
              {t('overview.activity')}
            </h2>
            {activity.length ? (
              <ul className="flex flex-col">
                {activity.map((a, i) => (
                  <li
                    key={i}
                    className="flex items-start justify-between gap-2 border-t border-line py-2.5 text-sm first:border-t-0 first:pt-0"
                  >
                    <span className="text-tx">
                      {t(`overview.event.${a.type}`)}
                      {a.customer_name ? ` · ${a.customer_name}` : ''}
                    </span>
                    <span className="shrink-0 text-xs text-tx-3">{fromNow(a.at, i18n.language)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-tx-3">{t('overview.noActivity')}</p>
            )}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="grid gap-4 sm:grid-cols-3">
        {QUICK_ACTIONS.map(({ to, key, Icon, accent }) => (
          <button
            key={to}
            onClick={() => navigate(to)}
            className="theme-t group flex items-center gap-3 rounded-card border border-line bg-surface p-4 text-start shadow-card transition hover:-translate-y-0.5 hover:border-violet/40 hover:shadow-bold"
          >
            <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-ctl ${accent}`}>
              <Icon size={20} />
            </span>
            <span className="font-semibold text-tx">{t(`overview.${key}`)}</span>
            <ChevronRight
              size={18}
              className="ms-auto text-tx-3 transition group-hover:translate-x-0.5 group-hover:text-violet-d rtl:rotate-180"
            />
          </button>
        ))}
      </div>
    </div>
  )
}
