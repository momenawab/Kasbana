// Main QR (finalize Phase A) — the merchant's one printed code. Electing a
// different card re-points it, so the poster on the counter never needs
// reprinting. Rotating the token DOES kill every printed poster, hence a confirm.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Copy, Printer, QrCode, RefreshCw } from 'lucide-react'
import { useCards } from '../cards/api'
import { useMainQr, useSetPrimaryCard, useRotateMainQr } from './api'
import { Select } from '../../components/Field'
import QrBlock from '../../components/QrBlock'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import EmptyState from '../../components/EmptyState'
import { Modal } from '../../components/Modal'
import { useToast } from '../../hooks/useToast'

export default function MainQr() {
  const { t } = useTranslation()
  const toast = useToast()
  const [copied, setCopied] = useState(false)
  const [confirmRotate, setConfirmRotate] = useState(false)

  const { data, isLoading } = useMainQr()
  const { data: cards } = useCards()
  const setPrimary = useSetPrimaryCard()
  const rotate = useRotateMainQr()

  // Only an ACTIVE card can take joins through the main QR — the backend
  // rejects anything else, so don't offer it here either.
  const activeCards = (cards || []).filter((c) => c.status === 'ACTIVE')
  const joinUrl = data?.join_url || ''
  const primaryId = data?.primary_card?.id || ''

  async function copy() {
    try {
      await navigator.clipboard.writeText(joinUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('qr.copyFailed'))
    }
  }

  function elect(cardId) {
    setPrimary.mutate(cardId || null, {
      onSuccess: () => toast.success(t('mainQr.saved')),
      onError: () => toast.error(t('mainQr.saveFailed')),
    })
  }

  function doRotate() {
    setConfirmRotate(false)
    rotate.mutate(undefined, {
      onSuccess: () => toast.success(t('mainQr.rotated')),
      onError: () => toast.error(t('mainQr.rotateFailed')),
    })
  }

  if (isLoading) return <Skeleton h={420} rounded="card" />

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 font-head text-2xl font-bold text-tx">{t('mainQr.title')}</h1>
      <p className="mb-5 text-sm text-tx-2">{t('mainQr.explainer')}</p>

      <div className="flex flex-col gap-5 rounded-card border border-line bg-surface p-6">
        <Select
          name="primary_card_id"
          label={t('mainQr.cardLabel')}
          hint={t('mainQr.cardHint')}
          value={primaryId}
          disabled={setPrimary.isPending || !activeCards.length}
          onChange={(e) => elect(e.target.value)}
          options={[
            { value: '', label: t('mainQr.noCard') },
            ...activeCards.map((c) => ({ value: c.id, label: c.name })),
          ]}
        />

        {!data?.primary_card ? (
          <EmptyState
            icon={QrCode}
            title={t('mainQr.emptyTitle')}
            body={activeCards.length ? t('mainQr.emptyBody') : t('mainQr.emptyNoActive')}
          />
        ) : (
          <>
            <div className="flex justify-center">
              <QrBlock value={joinUrl} size={240} downloadName="stampn-main-qr" />
            </div>

            <div className="flex w-full items-center gap-2 rounded-ctl border border-line bg-paper px-3 py-2">
              <span dir="ltr" className="flex-1 truncate text-sm text-tx-2">
                {joinUrl}
              </span>
              <Button size="sm" variant="ghost" iconStart={Copy} onClick={copy}>
                {copied ? t('qr.copied') : t('qr.copy')}
              </Button>
            </div>

            {data.poster_pdf_url && (
              <a href={data.poster_pdf_url} target="_blank" rel="noreferrer">
                <Button variant="ghost" iconStart={Printer} className="w-full">
                  {t('qr.poster')}
                </Button>
              </a>
            )}
          </>
        )}

        <div className="border-t border-line pt-4">
          <Button
            variant="ghost"
            iconStart={RefreshCw}
            onClick={() => setConfirmRotate(true)}
            disabled={rotate.isPending}
          >
            {t('mainQr.rotate')}
          </Button>
          <p className="mt-1 text-xs text-tx-3">{t('mainQr.rotateHint')}</p>
        </div>
      </div>

      <Modal
        open={confirmRotate}
        onClose={() => setConfirmRotate(false)}
        title={t('mainQr.rotateConfirmTitle')}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmRotate(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={doRotate}>{t('mainQr.rotateConfirmCta')}</Button>
          </div>
        }
      >
        <p className="text-sm text-tx-2">{t('mainQr.rotateConfirmBody')}</p>
      </Modal>
    </div>
  )
}
