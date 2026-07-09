// Enrollment QR (spec §14) — big QrBlock (download), copy join_url, poster link,
// WhatsApp share. Data from GET /cards/{id}/qr (1.6 — mock until prod promotion).
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Copy, Printer, MessageCircle, ArrowLeft, Palette } from 'lucide-react'
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
    <div className="mx-auto max-w-lg">
      <Button
        variant="ghost"
        iconStart={ArrowLeft}
        onClick={() => navigate(`/cards/${id}`)}
        className="mb-4"
      >
        {t('onboarding.back')}
      </Button>

      <div className="flex flex-col items-center gap-5 rounded-card border border-line bg-white p-6">
        <h1 className="font-head text-2xl font-bold text-tx">{t('qr.title')}</h1>

        {isLoading ? (
          <Skeleton h={240} w={240} rounded="card" />
        ) : (
          <>
            <QrBlock value={joinUrl} size={240} downloadName={`stampn-card-${id}`} />

            <div className="flex w-full items-center gap-2 rounded-ctl border border-line bg-paper px-3 py-2">
              <span dir="ltr" className="flex-1 truncate text-sm text-tx-2">
                {joinUrl}
              </span>
              <Button size="sm" variant="ghost" iconStart={Copy} onClick={copy}>
                {copied ? t('qr.copied') : t('qr.copy')}
              </Button>
            </div>

            <div className="flex w-full flex-col gap-2 sm:flex-row">
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
              className="w-full"
              onClick={() => navigate(`/cards/${id}/enroll-page`)}
            >
              {t('enrollTheme.editCardPage')}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
