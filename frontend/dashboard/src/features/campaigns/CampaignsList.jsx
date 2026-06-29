// Campaigns list (spec §14) — table of sent/scheduled campaigns. New → compose.
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, MessageSquare } from 'lucide-react'
import { useCampaigns } from './api'
import Table from '../../components/Table'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import EmptyState from '../../components/EmptyState'
import { fromNow } from '../../lib/format'

export default function CampaignsList() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { data: campaigns = [], isLoading } = useCampaigns()
  const lang = i18n.language

  const columns = [
    { key: 'channel', label: t('campaigns.channel'), render: (r) => <Badge tone="neutral">{r.channel}</Badge> },
    { key: 'audience', label: t('campaigns.audience') },
    { key: 'status', label: t('campaigns.statusCol'), render: (r) => <Badge tone="teal">{r.status}</Badge> },
    {
      key: 'sent_at',
      label: t('campaigns.sent'),
      render: (r) => (r.sent_at ? fromNow(r.sent_at, lang) : r.schedule_at ? t('campaigns.scheduled') : '—'),
    },
    {
      key: 'stats',
      label: t('campaigns.delivered'),
      render: (r) => <span className="font-num">{r.stats?.delivered ?? 0}</span>,
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-ink">{t('campaigns.title')}</h1>
        <Button iconStart={Plus} onClick={() => navigate('/campaigns/new')}>
          {t('campaigns.new')}
        </Button>
      </div>

      <Table
        columns={columns}
        rows={campaigns}
        loading={isLoading}
        emptyState={
          <EmptyState
            icon={MessageSquare}
            title={t('campaigns.emptyTitle')}
            body={t('campaigns.emptyBody')}
            action={
              <Button iconStart={Plus} onClick={() => navigate('/campaigns/new')}>
                {t('campaigns.new')}
              </Button>
            }
          />
        }
      />
    </div>
  )
}
