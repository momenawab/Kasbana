// Customer profile (spec §14) — header, stamp progress, timeline, manual
// stamp/redeem, send message, PDPL delete. stamp/redeem live (1.2); detail/
// timeline/message/delete are 1.6/1.7 (graceful).
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Plus, Minus, Trash2, MessageSquare, ArrowLeft } from 'lucide-react'
import { useCustomer, useTimeline, useStampActions } from './api'
import { normalizeError } from '../../lib/api'
import { useToast } from '../../hooks/useToast'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import Skeleton from '../../components/Skeleton'
import { Modal } from '../../components/Modal'
import { Textarea } from '../../components/Field'
import { arDigits, fromNow } from '../../lib/format'

export default function CustomerProfile() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { id } = useParams()
  const toast = useToast()
  const lang = i18n.language

  const { data: c, isLoading } = useCustomer(id)
  const { data: timeline = [] } = useTimeline(id)
  // redeem() exists in the api hook; wired once card rewards are surfaced here.
  const { stamp, message, remove } = useStampActions(id)

  const [msgOpen, setMsgOpen] = useState(false)
  const [text, setText] = useState('')

  async function doStamp(delta) {
    try {
      await stamp.mutateAsync(delta)
    } catch (err) {
      const { code, message: m } = normalizeError(err)
      toast.error(code === 'COOLDOWN_ACTIVE' ? t('profile.cooldown') : m)
    }
  }

  async function sendMessage() {
    try {
      await message.mutateAsync({ channel: 'PUSH', text })
      toast.success(t('profile.messageSent'))
      setMsgOpen(false)
      setText('')
    } catch (err) {
      toast.error(normalizeError(err).message)
    }
  }

  async function deleteCustomer() {
    if (!window.confirm(t('profile.deleteConfirm'))) return
    try {
      await remove.mutateAsync()
      toast.success(t('profile.deleted'))
      navigate('/customers')
    } catch (err) {
      toast.error(normalizeError(err).message)
    }
  }

  if (isLoading || !c) return <Skeleton h={300} rounded="card" />

  const ready = c.stamp_count >= c.stamps_required

  return (
    <div className="flex flex-col gap-5">
      <Button variant="ghost" iconStart={ArrowLeft} onClick={() => navigate('/customers')} className="self-start">
        {t('onboarding.back')}
      </Button>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-card border border-line bg-surface p-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-head text-2xl font-bold text-tx">{c.customer_name || t('customers.noName')}</h1>
            {c.wallet_platform && <Badge tone="neutral">{c.wallet_platform}</Badge>}
            {ready && <Badge tone="success">{t('profile.rewardReady')}</Badge>}
          </div>
          <p dir="ltr" className="mt-1 text-sm text-tx-2">{c.customer_phone}</p>
          <p className="mt-1 text-sm text-tx-3">
            {t('profile.joined')}: {fromNow(c.enrolled_at, lang)}
            {c.birthday ? ` · ${t('profile.birthday')}: ${c.birthday}` : ''}
          </p>
        </div>
        <div className="text-end">
          <div className="font-num text-3xl text-tx">
            {arDigits(`${c.stamp_count}/${c.stamps_required}`, lang)}
          </div>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="ghost" iconStart={Minus} onClick={() => doStamp(-1)} loading={stamp.isPending} />
            <Button size="sm" iconStart={Plus} onClick={() => doStamp(1)} loading={stamp.isPending} />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        <Button variant="ghost" iconStart={MessageSquare} onClick={() => setMsgOpen(true)}>
          {t('profile.message')}
        </Button>
        <Button variant="danger" iconStart={Trash2} onClick={deleteCustomer} loading={remove.isPending}>
          {t('profile.delete')}
        </Button>
      </div>

      {/* Timeline */}
      <div className="rounded-card border border-line bg-surface p-5">
        <h2 className="mb-3 font-head font-semibold text-tx">{t('profile.timeline')}</h2>
        {timeline.length ? (
          <ul className="flex flex-col gap-3">
            {timeline.map((e, i) => (
              <li key={i} className="flex items-start justify-between gap-3 border-b border-line pb-2 text-sm last:border-0">
                <div>
                  <span className="text-tx">{t(`profile.event.${e.event_type}`)}</span>
                  {e.staff_name ? <span className="text-tx-3"> · {e.staff_name}</span> : ''}
                  {e.location ? <span className="text-tx-3"> · {e.location}</span> : ''}
                </div>
                <span className="shrink-0 text-xs text-tx-3">{fromNow(e.at, lang)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-tx-3">{t('profile.noTimeline')}</p>
        )}
      </div>

      <Modal
        open={msgOpen}
        onClose={() => setMsgOpen(false)}
        title={t('profile.message')}
        footer={
          <Button onClick={sendMessage} loading={message.isPending} disabled={!text.trim()} className="w-full">
            {t('profile.send')}
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-tx-3">{t('profile.channelPush')}</p>
          <Textarea name="text" label={t('profile.text')} value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      </Modal>
    </div>
  )
}
