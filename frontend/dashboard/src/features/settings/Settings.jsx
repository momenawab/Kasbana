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
import { Input, Textarea } from '../../components/Field'
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
        phone: data.phone || '',
        facebook_url: data.facebook_url || '',
        instagram_url: data.instagram_url || '',
        whatsapp: data.whatsapp || '',
        tiktok_url: data.tiktok_url || '',
        terms_url: data.terms_url || '',
        branches: data.branches || '',
      })
  }, [data])

  const save = useMutation({
    mutationFn: async () => {
      // The API takes phone nested under `contact`; everything else is top-level.
      const { phone, ...rest } = form
      return (await api.patch('/settings/business', { ...rest, contact: { phone } })).data
    },
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
          <span className="text-sm font-semibold text-tx">{t('settings.brandedEnroll')}</span>
          {!branded && (
            <button
              type="button"
              onClick={() => requireFeature('custom_branding')}
              className="text-xs text-violet-d underline"
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

      {/* Contact & social links — shown on the wallet pass back. Each optional;
          only filled-in fields appear on the pass. */}
      <div className="rounded-ctl border border-line p-3">
        <div className="mb-2 text-sm font-semibold text-tx">{t('settings.passLinks')}</div>
        <p className="mb-3 text-xs text-tx-3">{t('settings.passLinksHint')}</p>
        <div className="flex flex-col gap-3">
          <Input
            name="phone"
            label={t('settings.phone')}
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
          <Input
            name="facebook_url"
            label={t('settings.facebook')}
            placeholder="https://facebook.com/..."
            value={form.facebook_url}
            onChange={(e) => setForm({ ...form, facebook_url: e.target.value })}
          />
          <Input
            name="instagram_url"
            label={t('settings.instagram')}
            placeholder="https://instagram.com/..."
            value={form.instagram_url}
            onChange={(e) => setForm({ ...form, instagram_url: e.target.value })}
          />
          <Input
            name="whatsapp"
            label={t('settings.whatsapp')}
            placeholder="+20 1x xxxx xxxx"
            value={form.whatsapp}
            onChange={(e) => setForm({ ...form, whatsapp: e.target.value })}
          />
          <Input
            name="tiktok_url"
            label={t('settings.tiktok')}
            placeholder="https://tiktok.com/@..."
            value={form.tiktok_url}
            onChange={(e) => setForm({ ...form, tiktok_url: e.target.value })}
          />
          <Input
            name="terms_url"
            label={t('settings.terms')}
            placeholder="https://..."
            value={form.terms_url}
            onChange={(e) => setForm({ ...form, terms_url: e.target.value })}
          />
          <Textarea
            name="branches"
            label={t('settings.branches')}
            hint={t('settings.branchesHint')}
            rows={3}
            value={form.branches}
            onChange={(e) => setForm({ ...form, branches: e.target.value })}
          />
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
            className={`rounded-ctl border px-4 py-2 ${form.language === l ? 'border-violet bg-violet-bg text-violet-d' : 'border-line'}`}
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
      <h1 className="font-head text-2xl font-bold text-tx">{t('settings.title')}</h1>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      <div className="rounded-card border border-line bg-surface p-5">
        {tab === 'business' && <BusinessTab />}
        {tab === 'enroll' && <EnrollThemeEditor />}
        {tab === 'account' && <AccountTab />}
        {tab === 'password' && <PasswordTab />}
      </div>
    </div>
  )
}
