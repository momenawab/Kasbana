// Settings (spec §14) — tabs: Business (branding/contact), Account (language +
// notifications), Password. All live backend (1.5). Language tab flips dir.
import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Check, LogOut } from 'lucide-react'
import api, { normalizeError } from '../../lib/api'
import { setTokens } from '../../lib/auth'
import { setLang } from '../../lib/i18n'
import { daysUntil, fmtDate } from '../../lib/format'
import { useToast } from '../../hooks/useToast'
import { usePlan } from '../../hooks/usePlan'
import { useAuth } from '../../hooks/useAuth'
import Tabs from '../../components/Tabs'
import { Input, Textarea } from '../../components/Field'
import { Toggle } from '../../components/Toggle'
import ColorPicker from '../../components/ColorPicker'
import FileUpload from '../../components/FileUpload'
import Button from '../../components/Button'
import WalletPreview from '../../components/WalletPreview'
import EnrollThemeEditor from '../enroll-theme/EnrollThemeEditor'

// Every tab is a two-column grid: the editable form on the left, and on the
// right a rail that answers "what does this actually change?" — a live pass
// preview (Business), the account facts the prefs apply to (Account), or the
// rules the new password is checked against (Password). Below `lg` the rail
// stacks under the form.
function Section({ title, hint, action, className = '', children }) {
  return (
    <div className={`rounded-ctl border border-line p-3 ${className}`}>
      <div className="mb-1 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-tx">{title}</span>
        {action}
      </div>
      {hint && <p className="mb-3 text-xs text-tx-3">{hint}</p>}
      <div className={`flex flex-col gap-3 ${hint ? '' : 'mt-2'}`}>{children}</div>
    </div>
  )
}

// The right rail of the Business tab: the merchant's branding rendered on the
// real pass mock (same component the card designer uses), plus the pass-back
// links exactly as the contact fields fill them in. Every edit lands here live,
// so "what does this color/logo/link do?" is answered without leaving the page.
function BrandPreview({ form }) {
  const { t } = useTranslation()
  const [platform, setPlatform] = useState('APPLE')

  const links = [
    { label: t('settings.address'), value: form.address },
    { label: t('settings.phone'), value: form.phone, ltr: true },
    { label: t('settings.whatsapp'), value: form.whatsapp, ltr: true },
    { label: t('settings.facebook'), value: form.facebook_url, ltr: true },
    { label: t('settings.instagram'), value: form.instagram_url, ltr: true },
    { label: t('settings.tiktok'), value: form.tiktok_url, ltr: true },
    { label: t('settings.terms'), value: form.terms_url, ltr: true },
    { label: t('settings.branches'), value: form.branches },
  ].filter((l) => (l.value || '').trim())

  return (
    <div className="flex flex-col gap-4 rounded-ctl border border-line bg-paper p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-tx">{t('settings.preview')}</div>
          <p className="text-xs text-tx-3">{t('settings.previewHint')}</p>
        </div>
        <div className="flex shrink-0 gap-1">
          <Button
            size="sm"
            variant={platform === 'APPLE' ? 'primary' : 'ghost'}
            onClick={() => setPlatform('APPLE')}
          >
            Apple
          </Button>
          <Button
            size="sm"
            variant={platform === 'GOOGLE' ? 'primary' : 'ghost'}
            onClick={() => setPlatform('GOOGLE')}
          >
            Google
          </Button>
        </div>
      </div>

      <div className="flex justify-center">
        <WalletPreview
          platform={platform}
          logoUrl={form.logo_url}
          colorBg={form.color_bg}
          colorFg={form.color_fg}
          merchantName={form.name || t('enrollTheme.sampleMerchant')}
          programName={t('enrollTheme.sampleProgram')}
          rewardTitle={t('enrollTheme.sampleReward')}
          stampCount={3}
          stampsRequired={8}
        />
      </div>

      <div className="rounded-ctl border border-line bg-surface p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-tx-3">
          {t('settings.passBackTitle')}
        </div>
        {links.length === 0 ? (
          <p className="text-xs text-tx-3">{t('settings.passBackEmpty')}</p>
        ) : (
          <dl className="flex flex-col gap-2">
            {links.map((l) => (
              <div key={l.label} className="flex items-baseline justify-between gap-3">
                <dt className="shrink-0 text-xs text-tx-3">{l.label}</dt>
                <dd
                  dir={l.ltr ? 'ltr' : undefined}
                  className="min-w-0 truncate text-xs text-tx-2"
                  title={l.value}
                >
                  {l.value.split('\n').filter(Boolean).join(' · ')}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </div>
  )
}

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
        legal_name: data.legal_name || '',
        logo_url: data.logo_url || '',
        address: data.address || '',
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
      const { phone, enroll_headline, enroll_tagline, ...rest } = form
      const payload = { ...rest, contact: { phone } }
      // Enrollment copy is a custom_branding field — posting it on a plan that
      // can't set it is a paid-feature attempt, not a business-details save.
      if (branded) Object.assign(payload, { enroll_headline, enroll_tagline })
      return (await api.patch('/settings/business', payload)).data
    },
    onSuccess: () => {
      toast.success(t('settings.saved'))
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  if (!form) return null
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Editor column */}
      <div className="flex min-w-0 flex-col gap-4">
        <Section title={t('settings.sectionIdentity')}>
          <Input
            name="name"
            label={t('settings.businessName')}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            name="legal_name"
            label={t('settings.legalName')}
            value={form.legal_name}
            onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
          />
          <FileUpload
            label={t('settings.logo')}
            initial={form.logo_url || null}
            onUploaded={(url) => setForm({ ...form, logo_url: url })}
          />
          <Input
            name="address"
            label={t('settings.address')}
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
          />
        </Section>

        {/* Brand colors — stacked full-width so the swatch, hex field and
            presets have room to breathe. */}
        <Section title={t('settings.brandColors')} hint={t('settings.brandColorsHint')}>
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
        </Section>

        {/* Branded enrollment page — custom_branding plans (Growth+). */}
        <Section
          title={t('settings.brandedEnroll')}
          action={
            !branded && (
              <button
                type="button"
                onClick={() => requireFeature('custom_branding')}
                className="shrink-0 text-xs text-violet-d underline"
              >
                {t('settings.upgradeToUnlock')}
              </button>
            )
          }
        >
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
        </Section>

        {/* Contact & social links — shown on the wallet pass back. Each optional;
            only filled-in fields appear on the pass (and in the rail preview). */}
        <Section title={t('settings.passLinks')} hint={t('settings.passLinksHint')}>
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
        </Section>

        <Button onClick={() => save.mutate()} loading={save.isPending} className="self-start">
          {t('settings.save')}
        </Button>
      </div>

      {/* Preview rail — sticky so it stays in view for the whole form scroll.
          The rail spans the viewport height and `zoom` (not transform:scale)
          shrinks the real layout box, so the whole panel — pass mock plus the
          pass-back list under it — fits without its tail being cut off. */}
      <div className="min-w-0 lg:sticky lg:top-20 lg:h-[calc(100dvh-6rem)] lg:overflow-y-auto lg:self-start">
        <div className="w-full" style={{ zoom: 0.85 }}>
          <BrandPreview form={form} />
        </div>
      </div>
    </div>
  )
}

function AccountTab() {
  const { t, i18n } = useTranslation()
  const toast = useToast()
  const { role, logout, merchant } = useAuth()
  const { plan } = usePlan()
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

  // PDPL data export — owner-only. Fetch the JSON (with auth) and save it as a
  // file client-side; a plain <a href> can't send the Bearer token.
  const exporting = useMutation({
    mutationFn: async () => (await api.get('/settings/account/export')).data,
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `stampn-${data?.merchant?.slug || 'account'}-data.json`
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: () => toast.error(t('settings.exportFailed')),
  })

  if (!form) return null

  // The facts these preferences apply to. Read-only here on purpose — the plan
  // is changed in Billing and the role by an owner in Team; this rail just says
  // which account you're editing, and links to where each is actually changed.
  const onTrial = plan === 'trial' && merchant?.trial_ends_at
  const facts = [
    { label: t('settings.overviewBusiness'), value: merchant?.name },
    {
      label: t('settings.overviewPlan'),
      value: plan ? t(`billing.plan.${plan}`, { defaultValue: plan }) : null,
      to: '/billing',
      cta: t('settings.managePlan'),
    },
    {
      label: t('settings.overviewTrialEnds'),
      value: onTrial
        ? t('settings.trialEndsOn', {
            date: fmtDate(merchant.trial_ends_at, i18n.language),
            count: daysUntil(merchant.trial_ends_at),
          })
        : null,
    },
    { label: t('settings.overviewRole'), value: role ? t(`roles.${role}`) : null },
  ].filter((f) => f.value)

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Preferences column */}
      <div className="flex min-w-0 flex-col gap-4">
        <Section title={t('common.language')}>
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
        </Section>

        <Section title={t('settings.notifSection')}>
          <div>
            <Toggle
              checked={form.notifications.email}
              onChange={(v) =>
                setForm({ ...form, notifications: { ...form.notifications, email: v } })
              }
              label={t('settings.notifEmail')}
            />
            <p className="mt-1 text-xs text-tx-3">{t('settings.notifEmailHint')}</p>
          </div>
          {/* No WhatsApp toggle: the capability is off on every plan and the
              adapter is dormant, so it could only ever be a no-op. The stored
              preference rides along in `form.notifications` for when the channel
              comes back. */}
        </Section>

        <Button onClick={() => save.mutate()} loading={save.isPending} className="self-start">
          {t('settings.save')}
        </Button>
      </div>

      {/* Account rail */}
      <div className="flex min-w-0 flex-col gap-4">
        {facts.length > 0 && (
          <Section title={t('settings.accountOverview')} className="bg-paper">
            <dl className="flex flex-col gap-3">
              {facts.map((f) => (
                <div key={f.label} className="flex items-baseline justify-between gap-3">
                  <dt className="shrink-0 text-xs text-tx-3">{f.label}</dt>
                  <dd className="flex min-w-0 items-baseline gap-2">
                    <span className="truncate text-sm text-tx">{f.value}</span>
                    {f.to && (
                      <Link to={f.to} className="shrink-0 text-xs text-violet-d underline">
                        {f.cta}
                      </Link>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </Section>
        )}

        {role === 'OWNER' && (
          <Section title={t('settings.dataSection')} hint={t('settings.exportDataHint')}>
            <Button
              variant="secondary"
              onClick={() => exporting.mutate()}
              loading={exporting.isPending}
              className="self-start"
            >
              {t('settings.exportData')}
            </Button>
          </Section>
        )}

        {/* Sign out — phone only. The sidebar (`hidden md:flex`) carries logout on
            desktop, so this is its exact complement: `md:hidden` means logout is
            reachable at every width, and never shown twice. */}
        <Section
          title={t('settings.sessionSection')}
          hint={t('settings.logoutHint')}
          className="md:hidden"
        >
          <Button variant="danger" onClick={logout} className="self-start">
            <LogOut size={16} />
            {t('common.logout')}
          </Button>
        </Section>
      </div>
    </div>
  )
}

// One checklist row. Unmet rules stay grey rather than red: the list is guidance
// while typing, not a rejected submission.
function Rule({ met, children }) {
  return (
    <li className="flex items-start gap-2">
      <span
        className={`mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
          met ? 'border-violet bg-violet text-white' : 'border-line text-transparent'
        }`}
      >
        <Check size={11} strokeWidth={3} />
      </span>
      <span className={`text-xs ${met ? 'text-tx-2' : 'text-tx-3'}`}>{children}</span>
    </li>
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
    onSuccess: (data) => {
      // The server revoked every session (incl. this device's old tokens) and
      // returned a fresh pair — adopt it so this device stays signed in.
      if (data?.access && data?.refresh) setTokens({ access: data.access, refresh: data.refresh })
      toast.success(t('settings.passwordChanged'))
      setCurrent('')
      setNext('')
    },
    onError: (err) => toast.error(normalizeError(err).message),
  })

  // Mirrors the server's only hard rule (min 8, see PasswordChangeSerializer);
  // the rest is advice, so nothing here gates the button beyond what the API
  // itself enforces.
  const rules = [
    { key: 'pwRuleLength', met: next.length >= 8 },
    { key: 'pwRuleDifferent', met: next.length > 0 && next !== current },
    { key: 'pwRuleMix', met: /[a-z]/i.test(next) && /[0-9]/.test(next) },
    { key: 'pwRuleLong', met: next.length >= 12 },
  ]

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Form column */}
      <div className="flex min-w-0 flex-col gap-4">
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
          className="self-start"
        >
          {t('settings.changePassword')}
        </Button>
      </div>

      {/* Guidance rail — the rules the new password is checked against, ticking
          live as it's typed, plus what the change does to other sessions. */}
      <div className="flex min-w-0 flex-col gap-4">
        <Section title={t('settings.pwRules')} className="bg-paper">
          <ul className="flex flex-col gap-2">
            {rules.map((r) => (
              <Rule key={r.key} met={r.met}>
                {t(`settings.${r.key}`)}
              </Rule>
            ))}
          </ul>
        </Section>

        <Section title={t('settings.pwDevices')}>
          <p className="text-xs text-tx-3">{t('settings.pwDevicesHint')}</p>
        </Section>
      </div>
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
