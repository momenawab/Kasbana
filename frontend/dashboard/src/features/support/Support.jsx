// Merchant support (finalize Phase B) — send the team a message and see the
// status of past ones. Replies arrive by email (handled admin-side). The whole
// screen is arealess: every role can reach support.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LifeBuoy, Send } from 'lucide-react'
import { useSupportMessages, useSendSupportMessage } from './api'
import { Input, Textarea } from '../../components/Field'
import Button from '../../components/Button'
import Badge from '../../components/Badge'
import Skeleton from '../../components/Skeleton'
import EmptyState from '../../components/EmptyState'
import { useToast } from '../../hooks/useToast'

const STATUS_TONE = { new: 'violet', read: 'teal', replied: 'success' }

export default function Support() {
  const { t } = useTranslation()
  const toast = useToast()
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')

  const { data: messages, isLoading } = useSupportMessages()
  const send = useSendSupportMessage()

  function submit(e) {
    e.preventDefault()
    if (!subject.trim() || !message.trim()) return
    send.mutate(
      { subject: subject.trim(), message: message.trim() },
      {
        onSuccess: () => {
          setSubject('')
          setMessage('')
          toast.success(t('support.sent'))
        },
        onError: () => toast.error(t('support.sendFailed')),
      }
    )
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 font-head text-2xl font-bold text-tx">{t('support.title')}</h1>
      <p className="mb-5 text-sm text-tx-2">{t('support.explainer')}</p>

      <form
        onSubmit={submit}
        className="flex flex-col gap-4 rounded-card border border-line bg-surface p-6"
      >
        <Input
          name="subject"
          label={t('support.subject')}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          maxLength={200}
          required
        />
        <Textarea
          name="message"
          label={t('support.message')}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={5}
          required
        />
        <Button
          type="submit"
          iconStart={Send}
          loading={send.isPending}
          disabled={!subject.trim() || !message.trim()}
          className="self-start"
        >
          {t('support.send')}
        </Button>
      </form>

      <h2 className="mb-3 mt-8 font-head text-lg font-semibold text-tx">{t('support.history')}</h2>
      {isLoading ? (
        <Skeleton h={120} rounded="card" />
      ) : !messages?.length ? (
        <EmptyState icon={LifeBuoy} title={t('support.emptyTitle')} body={t('support.emptyBody')} />
      ) : (
        <ul className="flex flex-col gap-3">
          {messages.map((m) => (
            <li key={m.id} className="rounded-card border border-line bg-surface p-4">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-head font-semibold text-tx">{m.subject}</span>
                <Badge tone={STATUS_TONE[m.status] || 'neutral'}>
                  {t(`support.status.${m.status}`)}
                </Badge>
              </div>
              <p className="whitespace-pre-wrap text-sm text-tx-2">{m.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
