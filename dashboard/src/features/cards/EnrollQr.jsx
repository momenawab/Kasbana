// Enrollment QR (spec §14) — big QrBlock (download), copy join_url, poster link,
// WhatsApp share. Data from GET /cards/{id}/qr (1.6 — mock until prod promotion).
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Copy, Printer, MessageCircle, ArrowLeft, Palette, QrCode } from 'lucide-react'
import api from '../../lib/api'
import QrBlock from '../../components/QrBlock'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import { useToast } from '../../hooks/useToast'

export default function EnrollQr() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const toast = useToast()
  const [copied, setCopied] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['cards', id, 'qr'],
    queryFn: async () => (await api.get(`/cards/${id}/qr`)).data,
    enabled: Boolean(id),
  })

  const joinUrl = data?.join_url || ''

  async function copy() {
    try {
      await navigator.clipboard.writeText(joinUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('qr.copyFailed'))
    }
  }

  const waUrl = `https://wa.me/?text=${encodeURIComponent(`${t('qr.shareMsg')} ${joinUrl}`)}`

  return (
    <div className="mx-auto max-w-lg md:max-w-3xl">
      <Button
        variant="ghost"
        iconStart={ArrowLeft}
        onClick={() => navigate(`/cards/${id}`)}
        className="mb-3"
      >
        {t('onboarding.back')}
      </Button>

      <h1 className="mb-3 font-head text-2xl font-bold text-tx">{t('qr.title')}</h1>

      {/* Same shape as Main QR: on desktop the code takes its own column beside
          the actions, because stacking them ran the last two buttons past the
          fold on a 768px-tall laptop. Placement is explicit rather than a DOM
          reorder, so phones keep the stacked order: code → link → share. */}
      <div className="grid gap-4 rounded-card border border-line bg-surface p-5 md:grid-cols-[auto_1fr] md:gap-x-6">
        {isLoading ? (
          <Skeleton h={240} w={240} rounded="card" />
        ) : (
          <>
            <div className="flex justify-center md:col-start-1 md:row-span-4 md:row-start-1 md:self-center">
              {/* Exported at 320px so the downloadable PNG stays print-sharp
                  even though it is displayed small. */}
              <QrBlock
                value={joinUrl}
                size={320}
                displaySize={208}
                downloadName={`stampn-card-${id}`}
              />
            </div>

            <div className="flex w-full items-center gap-2 self-end rounded-ctl border border-line bg-paper px-3 py-2 md:col-start-2 md:row-start-1">
              <span dir="ltr" className="flex-1 truncate text-sm text-tx-2">
                {joinUrl}
              </span>
              <Button size="sm" variant="ghost" iconStart={Copy} onClick={copy}>
                {copied ? t('qr.copied') : t('qr.copy')}
              </Button>
            </div>

            <div className="flex w-full flex-col gap-2 sm:flex-row md:col-start-2 md:row-start-2">
              <Button
                variant="ghost"
                iconStart={Printer}
                className="flex-1"
                onClick={() => navigate(`/cards/${id}/poster`)}
              >
                {t('qr.poster')}
              </Button>
              <a href={waUrl} target="_blank" rel="noreferrer" className="flex-1">
                <Button iconStart={MessageCircle} className="w-full">
                  {t('qr.whatsapp')}
                </Button>
              </a>
            </div>

            <Button
              variant="ghost"
              iconStart={Palette}
              className="w-full md:col-start-2 md:row-start-3"
              onClick={() => navigate(`/cards/${id}/enroll-page`)}
            >
              {t('enrollTheme.editCardPage')}
            </Button>

            {/* This QR is bound to this card forever. The main QR isn't. */}
            <Button
              variant="ghost"
              iconStart={QrCode}
              className="w-full self-start md:col-start-2 md:row-start-4"
              onClick={() => navigate('/main-qr')}
            >
              {t('qr.openMainQr')}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
