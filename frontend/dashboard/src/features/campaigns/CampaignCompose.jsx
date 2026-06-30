// Campaign compose (spec §14) — audience → message → send/schedule.
// Delivered free over the wallet push channel (no WhatsApp / no per-message cost).
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft } from 'lucide-react'
import { useSegments, useCreateCampaign } from './api'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import { Select, Textarea, Input } from '../../components/Field'
import Button from '../../components/Button'

export default function CampaignCompose() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const toast = useToast()
  const create = useCreateCampaign()
  const { data: segments = [] } = useSegments()

  const [audience, setAudience] = useState('')
  const [text, setText] = useState('')
  const [scheduleAt, setScheduleAt] = useState('')

  async function submit() {
    if (!text.trim()) {
      toast.error(t('compose.textRequired'))
      return
    }
    try {
      await create.mutateAsync({
        channel: 'PUSH',
        audience: audience || 'all',
        message: text,
        schedule_at: scheduleAt || null,
      })
      toast.success(scheduleAt ? t('compose.scheduled') : t('compose.sent'))
      navigate('/campaigns')
    } catch (err) {
      const { code, message } = normalizeError(err)
      toast.error(code === 'PLAN_LIMIT' ? t('compose.quotaExhausted') : message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Button variant="ghost" iconStart={ArrowLeft} onClick={() => navigate('/campaigns')} className="mb-4">
        {t('onboarding.back')}
      </Button>

      <div className="flex flex-col gap-4 rounded-card border border-line bg-white p-5">
        <h1 className="font-head text-2xl font-bold text-ink">{t('compose.title')}</h1>

        <Select
          name="audience"
          label={t('compose.audience')}
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
          options={[
            { value: '', label: t('compose.audienceAll') },
            ...segments.map((s) => ({ value: s.key, label: `${s.label} (${s.count})` })),
          ]}
        />

        <Textarea name="text" label={t('compose.message')} value={text} onChange={(e) => setText(e.target.value)} rows={4} />

        <Input
          name="schedule"
          type="datetime-local"
          label={t('compose.schedule')}
          value={scheduleAt}
          onChange={(e) => setScheduleAt(e.target.value)}
        />

        <Button onClick={submit} loading={create.isPending} className="w-full">
          {scheduleAt ? t('compose.scheduleBtn') : t('compose.sendBtn')}
        </Button>
      </div>
    </div>
  )
}
