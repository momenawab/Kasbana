import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { SIGNUP_ENDPOINT, DASHBOARD_LOGIN_URL } from '../config.js'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

// Material Symbols icon (decorative by default).
function Icon({ name, className = '' }) {
  return (
    <span className={`ms ${className}`} aria-hidden="true">
      {name}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Pre-launch checkout. Reached from a plan card (?plan=<key>&billing=<monthly|
// annual>). Collects the same fields as signup and creates the merchant account
// via the live /auth/signup endpoint (which starts a 14-day trial and returns
// tokens). The payment step is intentionally a facade until the Paymob gateway
// is connected: no card is collected and nothing is charged — the order-summary
// total is EGP 0.00 and the copy says so. On success we hand off to the
// dashboard login (email prefilled) with the password the owner just set.
//
// TEMPORARY: when real Paymob credentials land, replace the "complete checkout"
// step with the gateway redirect. Everything here is marketing-site-only, so
// removal is: delete this page, drop the /checkout route, and repoint the plan
// cards back to their previous target.
// ─────────────────────────────────────────────────────────────────────────────

const EMPTY = { business_name: '', name: '', email: '', phone: '', password: '', consent: false }

export default function Checkout() {
  const { lang, t } = useLang()
  const c = t.checkout
  const [params] = useSearchParams()

  const planKey = params.get('plan') || ''
  const annual = params.get('billing') === 'annual'
  // Plans are defined once, in i18n, and shared with the Pricing page.
  const plan = t.pricing.plans.find((p) => p.key === planKey && !p.custom)

  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState('idle') // idle | submitting | success | error
  const [feedback, setFeedback] = useState('')

  const fmt = (n) => n.toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-US')

  // No plan on the URL (or a custom/unknown plan) — send them to pick one rather
  // than render an empty order.
  if (!plan) {
    return (
      <>
        <Seo page="checkout" />
        <section className="section">
          <div className="container" style={{ textAlign: 'center', padding: '12vh 0' }}>
            <p className="section-sub">{c.missingPlan}</p>
            <Link to={PAGE_PATHS.pricing[lang]} className="btn btn-primary">
              {c.choosePlan}
            </Link>
          </div>
        </section>
      </>
    )
  }

  const price = annual ? plan.annual : plan.monthly
  const unit = annual ? c.perYear : c.perMonth

  function handleChange(e) {
    const { name, value, type, checked } = e.target
    setForm((f) => ({ ...f, [name]: type === 'checkbox' ? checked : value }))
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  function validate() {
    const next = {}
    if (!form.business_name.trim()) next.business_name = c.errors.business
    if (!form.name.trim()) next.name = c.errors.name
    if (!form.email.trim()) {
      next.email = c.errors.email
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = c.errors.emailInvalid
    }
    if (!form.phone.trim()) next.phone = c.errors.phone
    if (!form.password) {
      next.password = c.errors.password
    } else if (form.password.length < 8) {
      next.password = c.errors.passwordShort
    }
    if (!form.consent) next.consent = c.errors.consent
    return next
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFeedback('')

    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      setStatus('error')
      setFeedback(c.errors.fix)
      return
    }

    setStatus('submitting')
    try {
      const res = await fetch(SIGNUP_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          business_name: form.business_name.trim(),
          owner_name: form.name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim(),
          password: form.password,
          consent: true,
        }),
      })

      if (res.ok) {
        setStatus('success')
        return
      }
      // 409 → the email already has an account; point them at sign-in.
      if (res.status === 409) {
        setStatus('error')
        setErrors({ email: c.errors.exists })
        setFeedback(c.errors.exists)
        return
      }
      // Surface a field message from the API envelope where we can.
      const data = await res.json().catch(() => null)
      const fields = data?.error?.fields
      if (fields && typeof fields === 'object') {
        setErrors(fields)
        setStatus('error')
        setFeedback(c.errors.fix)
        return
      }
      setStatus('error')
      setFeedback(c.errors.generic)
    } catch {
      setStatus('error')
      setFeedback(c.errors.network)
    }
  }

  // Cross-origin handoff: the dashboard is a separate app/origin, so this is a
  // full navigation (not a router Link), with the email prefilled for sign-in.
  const dashboardHref = `${DASHBOARD_LOGIN_URL}?email=${encodeURIComponent(form.email.trim())}`

  return (
    <>
      <Seo page="checkout" />

      <section className="waitlist">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />
        <div className="ambient-orb orb-cyan" aria-hidden="true" />

        <div className="container waitlist-grid">
          {/* Left: order summary */}
          <div className="waitlist-pitch">
            <span className="pill">
              <Icon name="lock" className="pill-icon" />
              {c.pill}
            </span>

            <h1 className="waitlist-title">
              {c.title} <span className="text-gradient">{c.titleAccent}</span>
            </h1>

            <div className="glass-panel checkout-summary">
              <h2 className="checkout-summary-heading">{c.summaryHeading}</h2>

              <div className="checkout-line">
                <span className="checkout-line-label">{c.planLabel}</span>
                <span className="checkout-line-value">{plan.name}</span>
              </div>
              <div className="checkout-line">
                <span className="checkout-line-label">{c.billingLabel}</span>
                <span className="checkout-line-value">
                  {fmt(price)} {t.pricing.currency} {unit} · {annual ? c.annual : c.monthly}
                </span>
              </div>

              <div className="checkout-line checkout-total">
                <span className="checkout-line-label">{c.totalLabel}</span>
                <span className="checkout-line-value">{c.totalFree}</span>
              </div>

              <p className="checkout-trial">
                <Icon name="verified" /> {c.trialNote}
              </p>

              {plan.features?.length > 0 && (
                <>
                  <p className="checkout-includes">{c.includes}</p>
                  <ul className="checkout-features">
                    {plan.features.slice(0, 4).map((f) => (
                      <li key={f}>
                        <Icon name="check" className="pricing-check" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>

          {/* Right: details form → success confirmation */}
          <div className="glass-panel waitlist-card">
            {status === 'success' ? (
              <div className="waitlist-success" role="status" aria-live="polite">
                <div className="success-badge">
                  <Icon name="check" />
                </div>
                <span className="pill" style={{ marginBottom: '0.75rem' }}>
                  {c.success.badge}
                </span>
                <h2 className="success-title">{c.success.title}</h2>
                <p className="success-body">{c.success.body}</p>
                <p className="success-note">{c.success.note}</p>
                {/* Full navigation to the dashboard (different origin). */}
                <a href={dashboardHref} className="btn btn-primary btn-block">
                  {c.success.cta}
                  <Icon name="arrow_forward" />
                </a>
              </div>
            ) : (
              <>
                <div className="waitlist-card-head">
                  <h2 className="waitlist-card-title">{c.formHeading}</h2>
                  <p className="waitlist-card-sub">{c.formSub}</p>
                </div>

                <form className="form" onSubmit={handleSubmit} noValidate>
                  <div className="field">
                    <label htmlFor="business_name">{c.labels.business}</label>
                    <input
                      id="business_name"
                      name="business_name"
                      type="text"
                      value={form.business_name}
                      onChange={handleChange}
                      autoComplete="organization"
                      required
                      aria-invalid={errors.business_name ? 'true' : 'false'}
                      aria-describedby={errors.business_name ? 'business_name-error' : undefined}
                    />
                    {errors.business_name && (
                      <span className="field-error" id="business_name-error">
                        {errors.business_name}
                      </span>
                    )}
                  </div>

                  <div className="field">
                    <label htmlFor="name">{c.labels.name}</label>
                    <input
                      id="name"
                      name="name"
                      type="text"
                      value={form.name}
                      onChange={handleChange}
                      autoComplete="name"
                      required
                      aria-invalid={errors.name ? 'true' : 'false'}
                      aria-describedby={errors.name ? 'name-error' : undefined}
                    />
                    {errors.name && (
                      <span className="field-error" id="name-error">
                        {errors.name}
                      </span>
                    )}
                  </div>

                  <div className="field">
                    <label htmlFor="email">{c.labels.email}</label>
                    <input
                      id="email"
                      name="email"
                      type="email"
                      value={form.email}
                      onChange={handleChange}
                      autoComplete="email"
                      required
                      aria-invalid={errors.email ? 'true' : 'false'}
                      aria-describedby={errors.email ? 'email-error' : undefined}
                    />
                    {errors.email && (
                      <span className="field-error" id="email-error">
                        {errors.email}
                      </span>
                    )}
                  </div>

                  <div className="field">
                    <label htmlFor="phone">{c.labels.phone}</label>
                    <input
                      id="phone"
                      name="phone"
                      type="tel"
                      value={form.phone}
                      onChange={handleChange}
                      autoComplete="tel"
                      required
                      aria-invalid={errors.phone ? 'true' : 'false'}
                      aria-describedby={errors.phone ? 'phone-error' : undefined}
                    />
                    {errors.phone && (
                      <span className="field-error" id="phone-error">
                        {errors.phone}
                      </span>
                    )}
                  </div>

                  <div className="field">
                    <label htmlFor="password">{c.labels.password}</label>
                    <input
                      id="password"
                      name="password"
                      type="password"
                      value={form.password}
                      onChange={handleChange}
                      autoComplete="new-password"
                      required
                      minLength={8}
                      aria-invalid={errors.password ? 'true' : 'false'}
                      aria-describedby={errors.password ? 'password-error' : undefined}
                    />
                    {errors.password && (
                      <span className="field-error" id="password-error">
                        {errors.password}
                      </span>
                    )}
                  </div>

                  <div className="field field-checkbox">
                    <label htmlFor="consent" className="checkbox-label">
                      <input
                        id="consent"
                        name="consent"
                        type="checkbox"
                        checked={form.consent}
                        onChange={handleChange}
                        aria-invalid={errors.consent ? 'true' : 'false'}
                      />
                      <span>
                        {c.consent}{' '}
                        <Link to={PAGE_PATHS.privacy[lang]}>{t.nav.privacy}</Link>
                      </span>
                    </label>
                    {errors.consent && (
                      <span className="field-error" id="consent-error">
                        {errors.consent}
                      </span>
                    )}
                  </div>

                  {feedback && status === 'error' && (
                    <p className="form-feedback form-feedback-error" role="alert">
                      {feedback}
                    </p>
                  )}

                  <button
                    type="submit"
                    className="btn btn-primary btn-block"
                    disabled={status === 'submitting'}
                  >
                    {status === 'submitting' ? c.submitting : c.submit}
                  </button>

                  <p className="checkout-security">
                    <Icon name="lock" /> {c.securityNote}
                  </p>
                </form>
              </>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
