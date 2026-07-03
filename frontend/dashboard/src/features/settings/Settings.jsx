// Settings (spec §14) — tabs: Business (branding/contact), Account (language +
// notifications), Password. All live backend (1.5). Language tab flips dir.
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import api, { normalizeError } from '../../lib/api'
import { setLang } from '../../lib/i18n'
import { useToast } from '../../hooks/useToast'
import { usePlan } from '../../hooks/usePlan'
import Tabs from '../../components/Tabs'
import { Input } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import Button from '../../components/Button'
import EnrollThemeEditor from '../enroll-theme/EnrollThemeEditor'

function BusinessTab() {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const { can, requireFeature } = usePlan()
  const branded = can('custom_branding')
  const { data } = useQuery({
    queryKey: ['settings', 'business'],
    queryFn: async () => (await api.get('/settings/business')).data,
  })
  const [form, setForm] = useState(null)
  useEffect(() => {
    if (data)
      setForm({
        name: data.name || '',
        logo_url: data.logo_url || '',
        color_bg: data.color_bg || '#0E1B2A',
        color_fg: data.color_fg || '#FFFFFF',
        enroll_headline: data.enroll_headline || '',
        enroll_tagline: data.enroll_tagline || '',
      })
  }, [data])

  const save = useMutation({
    mutationFn: async () => (await api.patch('/settings/business', form)).data,
    onSuccess: () => {
      toast.success(t('settings.saved'))
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  if (!form) return null
  return (
    <div className="flex max-w-md flex-col gap-4">
      <Input
        name="name"
        label={t('settings.businessName')}
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <FileUpload
        label={t('settings.logo')}
        onUploaded={(url) => setForm({ ...form, logo_url: url })}
      />
      <div className="grid grid-cols-2 gap-3">
        <ColorPicker
          label={t('onboarding.colorBg')}
          value={form.color_bg}
          onChange={(v) => setForm({ ...form, color_bg: v })}
        />
        <ColorPicker
          label={t('onboarding.colorFg')}
          value={form.color_fg}
          onChange={(v) => setForm({ ...form, color_fg: v })}
        />
      </div>

      {/* Branded enrollment page — custom_branding plans (Growth+). */}
      <div className="rounded-ctl border border-line p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-semibold text-ink">{t('settings.brandedEnroll')}</span>
          {!branded && (
            <button
              type="button"
              onClick={() => requireFeature('custom_branding')}
              className="text-xs text-amber-d underline"
            >
              {t('settings.upgradeToUnlock')}
            </button>
          )}
        </div>
        <div className="flex flex-col gap-3">
          <Input
            name="enroll_headline"
            label={t('settings.enrollHeadline')}
            value={form.enroll_headline}
            disabled={!branded}
            onChange={(e) => setForm({ ...form, enroll_headline: e.target.value })}
          />
          <Input
            name="enroll_tagline"
            label={t('settings.enrollTagline')}
            value={form.enroll_tagline}
            disabled={!branded}
            onChange={(e) => setForm({ ...form, enroll_tagline: e.target.value })}
          />
          {branded && <p className="text-xs text-tx-3">{t('settings.brandedEnrollHint')}</p>}
        </div>
      </div>

      <Button onClick={() => save.mutate()} loading={save.isPending}>
        {t('settings.save')}
      </Button>
    </div>
  )
}

function AccountTab() {
  const { t, i18n } = useTranslation()
  const toast = useToast()
  const { data } = useQuery({
    queryKey: ['settings', 'account'],
    queryFn: async () => (await api.get('/settings/account')).data,
  })
  const [form, setForm] = useState(null)
  useEffect(() => {
    if (data)
      setForm({
        language: data.language || i18n.language,
        notifications: data.notifications || { email: true, whatsapp: false },
      })
  }, [data, i18n.language])

  const save = useMutation({
    mutationFn: async () => (await api.patch('/settings/account', form)).data,
    onSuccess: () => {
      toast.success(t('settings.saved'))
      setLang(form.language)
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  if (!form) return null
  return (
    <div className="flex max-w-md flex-col gap-4">
      <div className="flex gap-2">
        {['ar', 'en'].map((l) => (
          <button
            key={l}
            onClick={() => setForm({ ...form, language: l })}
            className={`rounded-ctl border px-4 py-2 ${form.language === l ? 'border-amber bg-amber-bg text-amber-d' : 'border-line'}`}
          >
            {l === 'ar' ? 'العربية' : 'English'}
          </button>
        ))}
      </div>
      <Toggle
        checked={form.notifications.email}
        onChange={(v) => setForm({ ...form, notifications: { ...form.notifications, email: v } })}
        label={t('settings.notifEmail')}
      />
      <Toggle
        checked={form.notifications.whatsapp}
        onChange={(v) =>
          setForm({ ...form, notifications: { ...form.notifications, whatsapp: v } })
        }
        label={t('settings.notifWhatsapp')}
      />
      <Button onClick={() => save.mutate()} loading={save.isPending}>
        {t('settings.save')}
      </Button>
    </div>
  )
}

function PasswordTab() {
  const { t } = useTranslation()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')

  const save = useMutation({
    mutationFn: async () =>
      (await api.post('/settings/account/password', { current, new: next })).data,
    onSuccess: () => {
      toast.success(t('settings.passwordChanged'))
      setCurrent('')
      setNext('')
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  return (
    <div className="flex max-w-md flex-col gap-4">
      <Input
        name="current"
        type="password"
        label={t('settings.currentPassword')}
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
      />
      <Input
        name="new"
        type="password"
        label={t('settings.newPassword')}
        value={next}
        onChange={(e) => setNext(e.target.value)}
      />
      <Button
        onClick={() => save.mutate()}
        loading={save.isPending}
        disabled={!current || next.length < 8}
      >
        {t('settings.changePassword')}
      </Button>
    </div>
  )
}

export default function Settings() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('business')
  const tabs = [
    { key: 'business', label: t('settings.tabBusiness') },
    { key: 'enroll', label: t('settings.tabEnroll') },
    { key: 'account', label: t('settings.tabAccount') },
    { key: 'password', label: t('settings.tabPassword') },
  ]
  return (
    <div className="flex flex-col gap-5">
      <h1 className="font-head text-2xl font-bold text-ink">{t('settings.title')}</h1>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      <div className="rounded-card border border-line bg-white p-5">
        {tab === 'business' && <BusinessTab />}
        {tab === 'enroll' && <EnrollThemeEditor />}
        {tab === 'account' && <AccountTab />}
        {tab === 'password' && <PasswordTab />}
      </div>
    </div>
  )
}
