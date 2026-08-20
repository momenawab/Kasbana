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

  if (isLoading) return <Skeleton h={340} rounded="card" />

  const elected = Boolean(data?.primary_card)

  const cardPicker = (
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
  )

  return (
    <div className="mx-auto max-w-lg md:max-w-3xl">
      <h1 className="font-head text-2xl font-bold text-tx">{t('mainQr.title')}</h1>
      <p className="mb-5 mt-1 text-sm text-tx-2">{t('mainQr.explainer')}</p>

      {/* Desktop gives the code its own column beside the controls, because
          stacking them ran the page past the fold on a 768px-tall laptop. The
          placement is explicit (rather than a DOM reorder) so phones keep the
          natural stacked story: pick a card → see its QR → copy the link.
          The controls sit in ONE row-2 stack rather than a row each: a row per
          control meant a merchant with no poster PDF still paid for its empty
          row, and the taller QR column smeared its slack across those auto rows.
          One `1fr` row + one flex gap keeps every gap at 16px in every state,
          and both columns hang from the same top edge. */}
      <div className="grid gap-4 rounded-card border border-line bg-surface p-5 md:grid-cols-[auto_1fr] md:grid-rows-[auto_1fr] md:gap-x-6">
        <div className="md:col-start-2 md:row-start-1">{cardPicker}</div>

        <div
          className={`flex justify-center md:col-start-1 md:row-span-2 md:row-start-1 md:self-start ${
            elected ? 'md:w-60' : 'md:w-72'
          }`}
        >
          {elected ? (
            // Exported at 320px so the downloadable PNG stays print-sharp even
            // though it is displayed small.
            <QrBlock value={joinUrl} size={320} displaySize={208} downloadName="stampn-main-qr" />
          ) : (
            <EmptyState
              icon={QrCode}
              title={t('mainQr.emptyTitle')}
              body={activeCards.length ? t('mainQr.emptyBody') : t('mainQr.emptyNoActive')}
            />
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-4 md:col-start-2 md:row-start-2">
          {elected && (
            <>
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
            <p className="mt-2 text-xs text-tx-3">{t('mainQr.rotateHint')}</p>
          </div>
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
