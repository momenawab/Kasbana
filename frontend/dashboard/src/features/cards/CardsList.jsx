// Cards list (spec §14) — grid of program cards with a mini WalletPreview.
// "New card" disabled at max_cards limit (opens UpgradeDrawer via usePlan).
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, CreditCard, Star } from 'lucide-react'
import { useCards } from './api'
import { useMainQr, useSetPrimaryCard } from '../main-qr/api'
import { usePlan } from '../../hooks/usePlan'
import { useAuth } from '../../hooks/useAuth'
import WalletPreview from '../../components/WalletPreview'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import EmptyState from '../../components/EmptyState'
import { useToast } from '../../hooks/useToast'

const STATUS_TONE = { ACTIVE: 'teal', DRAFT: 'violet', ARCHIVED: 'neutral' }

export default function CardsList() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const { merchant } = useAuth()
  const { requireRoom, atLimit } = usePlan()
  const { data: cards, isLoading } = useCards()
  const { data: mainQr } = useMainQr()
  const setPrimary = useSetPrimaryCard()

  function newCard() {
    // Guard: opens the UpgradeDrawer when at the plan's card limit.
    if (requireRoom('max_cards')) navigate('/cards/new')
  }

  function setAsMain(cardId) {
    setPrimary.mutate(cardId, {
      onSuccess: () => toast.success(t('mainQr.saved')),
      onError: () => toast.error(t('mainQr.saveFailed')),
    })
  }

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">{t('cards.title')}</h1>
        <Button iconStart={Plus} onClick={newCard} disabled={atLimit('max_cards')}>
          {t('cards.new')}
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} h={220} rounded="card" />
          ))}
        </div>
      ) : !cards?.length ? (
        <EmptyState
          icon={CreditCard}
          title={t('cards.emptyTitle')}
          body={t('cards.emptyBody')}
          action={
            <Button iconStart={Plus} onClick={newCard}>
              {t('cards.new')}
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((card) => {
            const isMain = mainQr?.primary_card?.id === card.id
            const canBeMain = card.status === 'ACTIVE'
            return (
              <div
                key={card.id}
                className="flex flex-col rounded-card border border-line bg-surface transition hover:shadow-bold"
              >
                <button
                  onClick={() => navigate(`/cards/${card.id}`)}
                  className="flex flex-col items-center gap-3 p-4 text-start"
                >
                  <div className="scale-90">
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
                  <div className="flex w-full items-center justify-between">
                    <span className="font-head font-semibold text-tx">{card.name}</span>
                    <Badge tone={STATUS_TONE[card.status] || 'neutral'}>
                      {t(`cards.status.${card.status}`)}
                    </Badge>
                  </div>
                  <div className="flex w-full justify-between text-sm text-tx-2">
                    <span>
                      {t('cards.holders')}: <span className="font-num">{card.holders ?? 0}</span>
                    </span>
                    <span>
                      {t('cards.stamps')}:{' '}
                      <span className="font-num">{card.stamps_issued ?? 0}</span>
                    </span>
                  </div>
                </button>

                <div className="flex items-center justify-center border-t border-line px-4 py-2">
                  {isMain ? (
                    <Badge tone="violet">{t('mainQr.badge')}</Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      iconStart={Star}
                      disabled={!canBeMain || setPrimary.isPending}
                      title={canBeMain ? undefined : t('mainQr.onlyActive')}
                      onClick={() => setAsMain(card.id)}
                    >
                      {t('mainQr.setAsMain')}
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
