// Printable enrollment poster (roadmap Phase 2) — a branded table-tent with the
// card's join QR. Uses the browser print dialog (Print → "Save as PDF" or print
// directly), so there's no server-side PDF dependency. The `.poster-sheet` is
// the only thing that prints (see the @media print rules in index.css).
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { QRCodeCanvas } from 'qrcode.react'
import { ArrowLeft, Printer } from 'lucide-react'
import api from '../../lib/api'
import { useCard } from './api'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'

export default function Poster() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const { data: card } = useCard(id)

  const { data: qr, isLoading } = useQuery({
    queryKey: ['cards', id, 'qr'],
    queryFn: async () => (await api.get(`/cards/${id}/qr`)).data,
    enabled: Boolean(id),
  })

  const joinUrl = qr?.join_url || ''
  const bg = card?.color_bg || '#0E1B2A'
  const fg = card?.color_fg || '#FFFFFF'

  if (isLoading || !card) return <Skeleton h={400} rounded="card" />

  return (
    <div className="mx-auto max-w-xl">
      {/* Controls — hidden when printing */}
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Button variant="ghost" iconStart={ArrowLeft} onClick={() => navigate(`/cards/${id}/qr`)}>
          {t('onboarding.back')}
        </Button>
        <Button iconStart={Printer} onClick={() => window.print()}>
          {t('poster.print')}
        </Button>
      </div>

      {/* The printable sheet */}
      <div
        className="poster-sheet mx-auto flex flex-col items-center gap-6 rounded-card p-10 text-center shadow-bold"
        style={{ backgroundColor: bg, color: fg }}
      >
        {card.logo_url && (
          <img src={card.logo_url} alt="" className="h-20 w-20 rounded-full object-cover" />
        )}
        <h1 className="font-head text-3xl font-bold">{card.name}</h1>
        <p className="text-lg opacity-90">{t('poster.headline')}</p>

        <div className="rounded-card bg-white p-5">
          <QRCodeCanvas value={joinUrl} size={240} fgColor="#0E1B2A" bgColor="#FFFFFF" />
        </div>

        <p className="text-base font-semibold">{t('poster.scan')}</p>
        {card.reward_title && (
          <p className="text-lg opacity-90">
            {t('poster.reward')}: <span className="font-bold">{card.reward_title}</span>
          </p>
        )}
        <p className="mt-2 text-sm opacity-70">{t('poster.powered')}</p>
      </div>
    </div>
  )
}
