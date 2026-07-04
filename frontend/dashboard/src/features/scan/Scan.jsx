// Cashier Scan / Till (spec — POS). Point the device camera at a customer's
// wallet QR (or type/scan it with a HID gun), see who they are + their balance,
// then Add stamp or Redeem the reward. Stamp/redeem hit the live loyalty engine;
// the wallet pass updates itself (Apple APNs / Google sync) on the backend.
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Gift, RotateCcw, CameraOff, ScanLine } from 'lucide-react'
import { useScanActions } from './api'
import { useQrScanner } from './useQrScanner'
import { cueScan, cueSuccess, cueError, primeFeedback } from './feedback'
import { normalizeError } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import Button from '../../components/Button'
import Badge from '../../components/Badge'
import { Input } from '../../components/Field'
import { Modal } from '../../components/Modal'
import { arDigits } from '../../lib/format'

export default function Scan() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language
  const toast = useToast()
  const { resolve, stamp, redeem } = useScanActions()
  const [card, setCard] = useState(null)
  const [manual, setManual] = useState('')
  const [amount, setAmount] = useState(1) // points to add (points cards only)
  const [confirmStamp, setConfirmStamp] = useState(false) // cooldown confirm popup
  const isPoints = card?.card_type === 'POINTS'

  // Unlock audio on the first touch so the scan beep can play (iOS/Chrome rule).
  useEffect(() => primeFeedback(), [])

  const handleCode = useCallback(
    async (code) => {
      if (resolve.isPending) return
      try {
        const data = await resolve.mutateAsync(code)
        cueScan()
        setAmount(1)
        setCard(data)
      } catch (err) {
        cueError()
        const { code: ec, message } = normalizeError(err)
        toast.error(ec === 'NOT_FOUND' ? t('scan.unknown') : message)
      }
    },
    [resolve, toast, t]
  )

  const scanning = !card
  const { videoRef, status } = useQrScanner({ active: scanning, onResult: handleCode })

  async function submitManual(e) {
    e.preventDefault()
    const code = manual.trim()
    setManual('')
    if (code) await handleCode(code)
  }

  async function doStamp(force = false) {
    const delta = isPoints ? Math.max(1, Number(amount) || 1) : 1
    try {
      const r = await stamp.mutateAsync({ customerCardId: card.customer_card_id, delta, force })
      setConfirmStamp(false)
      setCard((c) => ({
        ...c,
        stamp_count: r.stamp_count,
        stamps_required: r.stamps_required,
        reward_ready: r.reward_ready,
      }))
      cueSuccess()
      toast.success(t('scan.stamped'))
    } catch (err) {
      const { code: ec, message } = normalizeError(err)
      // A recent stamp isn't an error — ask the cashier to confirm the repeat
      // instead of blocking (replaces the hard cooldown). Other errors still toast.
      if (ec === 'COOLDOWN_ACTIVE' && !force) {
        setConfirmStamp(true)
        return
      }
      cueError()
      setConfirmStamp(false)
      toast.error(message)
    }
  }

  async function doRedeem() {
    try {
      const r = await redeem.mutateAsync({
        customerCardId: card.customer_card_id,
        rewardId: card.reward_id,
      })
      setCard((c) => ({ ...c, stamp_count: r.stamp_count, reward_ready: false }))
      cueSuccess()
      toast.success(t('scan.redeemed'))
    } catch (err) {
      cueError()
      const { code: ec, message } = normalizeError(err)
      toast.error(ec === 'REWARD_NOT_READY' ? t('scan.notReady') : message)
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-5">
      <div>
        <h1 className="font-head text-2xl font-bold text-ink">{t('scan.title')}</h1>
        <p className="mt-1 text-sm text-tx-3">{t('scan.subtitle')}</p>
      </div>

      {scanning ? (
        <>
          {/* Viewfinder */}
          <div className="relative aspect-square overflow-hidden rounded-card border border-line bg-ink">
            <video ref={videoRef} className="h-full w-full object-cover" muted playsInline />
            {/* Framing guide */}
            <div className="pointer-events-none absolute inset-8 rounded-xl border-2 border-white/70" />
            {status !== 'scanning' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-ink/80 p-6 text-center text-white">
                {status === 'starting' && <ScanLine className="animate-pulse" />}
                {(status === 'denied' || status === 'unsupported' || status === 'error') && (
                  <CameraOff />
                )}
                <p className="text-sm">{t(`scan.status.${status}`)}</p>
              </div>
            )}
            {resolve.isPending && (
              <div className="absolute inset-0 flex items-center justify-center bg-ink/70 text-white">
                <span className="text-sm">{t('scan.looking')}</span>
              </div>
            )}
          </div>

          {/* Manual entry / HID barcode gun */}
          <form onSubmit={submitManual} className="flex items-end gap-2">
            <div className="flex-1">
              <Input
                name="code"
                label={t('scan.manualLabel')}
                placeholder={t('scan.manualPlaceholder')}
                value={manual}
                onChange={(e) => setManual(e.target.value)}
                dir="ltr"
                autoComplete="off"
              />
            </div>
            <Button type="submit" loading={resolve.isPending} disabled={!manual.trim()}>
              {t('scan.lookup')}
            </Button>
          </form>
        </>
      ) : (
        /* Result */
        <div className="flex flex-col gap-5 rounded-card border border-line bg-white p-6">
          <div className="text-center">
            <h2 className="font-head text-2xl font-bold text-ink">
              {card.customer_name || t('scan.noName')}
            </h2>
            {card.reward_ready && (
              <div className="mt-2">
                <Badge tone="success">{t('scan.rewardReady')}</Badge>
              </div>
            )}
          </div>

          <div className="text-center">
            <div className="font-num text-5xl text-ink">
              {arDigits(`${card.stamp_count}/${card.stamps_required}`, lang)}
            </div>
            <div className="mt-1 text-sm text-tx-3">
              {isPoints ? t('scan.points') : t('scan.stamps')}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            {isPoints && (
              <div className="mx-auto w-32">
                <Input
                  name="amount"
                  type="number"
                  min={1}
                  label={t('scan.amount')}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
            )}
            <Button size="lg" iconStart={Plus} onClick={doStamp} loading={stamp.isPending}>
              {isPoints
                ? t('scan.addPoints', { n: Math.max(1, Number(amount) || 1) })
                : t('scan.addStamp')}
            </Button>
            <Button
              size="lg"
              variant="secondary"
              iconStart={Gift}
              onClick={doRedeem}
              loading={redeem.isPending}
              disabled={!card.reward_ready || !card.reward_id}
            >
              {card.reward_title
                ? t('scan.redeemNamed', { reward: card.reward_title })
                : t('scan.redeem')}
            </Button>
            <Button variant="ghost" iconStart={RotateCcw} onClick={() => setCard(null)}>
              {t('scan.next')}
            </Button>
          </div>
        </div>
      )}

      {/* Repeat-stamp confirm (replaces the hard cooldown block). */}
      <Modal
        open={confirmStamp}
        onClose={() => setConfirmStamp(false)}
        title={t('scan.confirmStampTitle')}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmStamp(false)}>
              {t('scan.confirmStampCancel')}
            </Button>
            <Button onClick={() => doStamp(true)} loading={stamp.isPending}>
              {t('scan.confirmStampYes')}
            </Button>
          </div>
        }
      >
        <p className="text-sm text-tx-2">
          {t('scan.confirmStampBody', { name: card?.customer_name || t('scan.noName') })}
        </p>
      </Modal>
    </div>
  )
}
