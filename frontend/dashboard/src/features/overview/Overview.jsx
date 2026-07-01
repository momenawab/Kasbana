// Overview (spec §14) — Direction-C data home: colored KPI tiles, dark chart
// card w/ metric switch, activity feed, quick actions. /analytics/summary is
// live (1.3); timeseries + activity are 1.6 (graceful fallback to empty).
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Users, Stamp, Gift, UserPlus, QrCode, MessageSquare } from 'lucide-react'
import api from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import KpiTile from '../../components/KpiTile'
import { ChartLine } from '../../components/Charts'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import EmptyState from '../../components/EmptyState'
import { fromNow } from '../../lib/format'

const METRICS = ['joins', 'stamps', 'redemptions']

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
      <h1 className="font-head text-2xl font-bold text-ink">
        {t('overview.greeting', { name: merchant?.name || '' })}
      </h1>

      {/* KPI tiles */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} h={120} rounded="card" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiTile label={t('overview.enrollments')} value={summary?.enrollments ?? 0} icon={Users} tone="amber" />
          <KpiTile label={t('overview.activeCards')} value={summary?.active_cards ?? 0} icon={Stamp} tone="teal" />
          <KpiTile label={t('overview.redemptions')} value={summary?.redemptions ?? 0} icon={Gift} tone="clay" />
          <KpiTile
            label={t('overview.repeatRate')}
            value={`${Math.round((summary?.repeat_rate ?? 0) * 100)}%`}
            icon={UserPlus}
            tone="ink"
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
          {/* Dark chart card (Direction C) */}
          <div className="relative overflow-hidden rounded-card bg-ink p-5 text-white shadow-bold lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-head font-semibold">{t('overview.trend')}</h2>
              <div className="flex gap-1">
                {METRICS.map((m) => (
                  <button
                    key={m}
                    onClick={() => setMetric(m)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      metric === m ? 'bg-amber text-ink' : 'bg-white/10 text-white/70'
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
          <div className="rounded-card border border-line bg-white p-5">
            <h2 className="mb-3 font-head font-semibold text-ink">{t('overview.activity')}</h2>
            {activity.length ? (
              <ul className="flex flex-col gap-3">
                {activity.map((a, i) => (
                  <li key={i} className="flex items-start justify-between gap-2 text-sm">
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
        <button onClick={() => navigate('/cards')} className="flex items-center gap-3 rounded-card bg-ink-2 p-4 text-white hover:bg-ink-3">
          <QrCode size={20} className="text-amber" />
          {t('overview.qaShareQr')}
        </button>
        <button onClick={() => navigate('/campaigns/new')} className="flex items-center gap-3 rounded-card bg-ink-2 p-4 text-white hover:bg-ink-3">
          <MessageSquare size={20} className="text-amber" />
          {t('overview.qaCampaign')}
        </button>
        <button onClick={() => navigate('/customers')} className="flex items-center gap-3 rounded-card bg-ink-2 p-4 text-white hover:bg-ink-3">
          <Users size={20} className="text-amber" />
          {t('overview.qaCustomers')}
        </button>
      </div>
    </div>
  )
}
