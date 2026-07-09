// Card detail (spec §14) — WalletPreview, stat KpiTiles (holders, stamps,
// rewards, completion), Apple/Google donut, links to edit + QR.
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Pencil, QrCode, Users, Stamp, Gift } from 'lucide-react'
import { useCard, useCardStats } from './api'
import { useAuth } from '../../hooks/useAuth'
import WalletPreview from '../../components/WalletPreview'
import KpiTile from '../../components/KpiTile'
import { ChartDonut } from '../../components/Charts'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'

const STATUS_TONE = { ACTIVE: 'teal', DRAFT: 'violet', ARCHIVED: 'neutral' }

export default function CardDetail() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const { merchant } = useAuth()
  const { data: card, isLoading } = useCard(id)
  const { data: stats } = useCardStats(id)

  if (isLoading || !card) {
    return <Skeleton h={400} rounded="card" />
  }

  const pct = stats?.completion_rate != null ? Math.round(stats.completion_rate * 100) : 0

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="font-head text-2xl font-bold text-slate">{card.name}</h1>
          <Badge tone={STATUS_TONE[card.status] || 'neutral'}>
            {t(`cards.status.${card.status}`)}
          </Badge>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" iconStart={QrCode} onClick={() => navigate(`/cards/${id}/qr`)}>
            {t('detail.qr')}
          </Button>
          <Button iconStart={Pencil} onClick={() => navigate(`/cards/${id}/edit`)}>
            {t('detail.edit')}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex justify-center rounded-card bg-paper p-5">
          <WalletPreview
            platform="APPLE"
            logoUrl={card.logo_url}
            colorBg={card.color_bg || '#0E1B2A'}
            colorFg={card.color_fg || '#FFFFFF'}
            merchantName={merchant?.name || ''}
            programName={card.name}
            rewardTitle={card.reward_title}
            stampsRequired={card.stamps_required}
            stampCount={0}
          />
        </div>

        <div className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <KpiTile label={t('detail.holders')} value={stats?.holders ?? card.holders ?? 0} icon={Users} tone="violet" />
            <KpiTile label={t('detail.stampsIssued')} value={stats?.stamps_issued ?? card.stamps_issued ?? 0} icon={Stamp} tone="teal" />
            <KpiTile label={t('detail.rewardsRedeemed')} value={stats?.rewards_redeemed ?? card.rewards_redeemed ?? 0} icon={Gift} tone="fuchsia" />
            <KpiTile label={t('detail.completion')} value={`${pct}%`} tone="slate" />
          </div>

          {(stats?.apple_count != null || stats?.google_count != null) && (
            <div className="mt-4 rounded-card border border-line bg-white p-4">
              <h3 className="mb-2 font-head font-semibold text-slate">{t('detail.walletSplit')}</h3>
              <ChartDonut
                data={[
                  { name: 'Apple', value: stats?.apple_count ?? 0 },
                  { name: 'Google', value: stats?.google_count ?? 0 },
                ]}
                height={200}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
