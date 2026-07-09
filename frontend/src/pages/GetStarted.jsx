import { useState } from 'react'
import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { LEADS_ENDPOINT } from '../config.js'
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
// "Join the waitlist" experience. Collects name / email / phone / business and
// POSTs to the backend (/api/v1/leads). On success the card celebrates the
// visitor's reserved spot; the lead shows up in the Admin console (Leads).
// ─────────────────────────────────────────────────────────────────────────────

const EMPTY = { name: '', email: '', phone: '', business_name: '', botcheck: '' }

export default function GetStarted() {
  const { lang, t } = useLang()
  const g = t.getStarted

  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState('idle') // idle | submitting | success | error
  const [feedback, setFeedback] = useState('')

  function handleChange(e) {
    const { name, value } = e.target
    setForm((f) => ({ ...f, [name]: value }))
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  function validate() {
    const next = {}
    if (!form.name.trim()) next.name = g.errors.name
    if (!form.email.trim()) {
      next.email = g.errors.email
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = g.errors.emailInvalid
    }
    if (!form.phone.trim()) next.phone = g.errors.phone
    if (!form.business_name.trim()) next.business_name = g.errors.business
    return next
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setFeedback('')

    // Honeypot: a bot fills this hidden field — silently treat as success.
    if (form.botcheck) {
      setStatus('success')
      setForm(EMPTY)
      return
    }

    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) {
      setStatus('error')
      setFeedback(g.errors.fix)
      return
    }

    setStatus('submitting')

    try {
      const res = await fetch(LEADS_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          phone: form.phone,
          business_name: form.business_name,
          botcheck: form.botcheck,
        }),
      })

      if (res.ok) {
        setStatus('success')
        setForm(EMPTY)
      } else {
        setStatus('error')
        setFeedback(g.errors.generic)
      }
    } catch (err) {
      setStatus('error')
      setFeedback(g.errors.network)
    }
  }

  return (
    <>
      <Seo page="getStarted" />

      <section className="waitlist">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />
        <div className="ambient-orb orb-cyan" aria-hidden="true" />

        <div className="container waitlist-grid">
          {/* Left: the pitch */}
          <div className="waitlist-pitch">
            <span className="pill">
              <Icon name="bolt" className="pill-icon" />
              {g.pill}
            </span>

            <h1 className="waitlist-title">
              {g.title} <span className="text-gradient">{g.titleAccent}</span>
            </h1>

            <p className="waitlist-lead">{g.lead}</p>

            <ul className="waitlist-benefits">
              {g.benefits.map((b) => (
                <li className="waitlist-benefit" key={b}>
                  <Icon name="check_circle" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            <div className="social-proof">
              <span className="proof-dots" aria-hidden="true">
                <span className="proof-dot" />
                <span className="proof-dot" />
                <span className="proof-dot" />
              </span>
              <span>{g.socialProof}</span>
            </div>
          </div>

          {/* Right: the waitlist card (form → celebration on success) */}
          <div className="glass-panel waitlist-card">
            {status === 'success' ? (
              <div className="waitlist-success" role="status" aria-live="polite">
                <div className="success-badge">
                  <Icon name="check" />
                </div>
                <h2 className="success-title">{g.success.title}</h2>
                <p className="success-body">{g.success.body}</p>
                <span className="proof-dots" aria-hidden="true">
                  <span className="proof-dot" />
                  <span className="proof-dot" />
                  <span className="proof-dot" />
                </span>
                <p className="success-note">{g.success.note}</p>
                <Link to={PAGE_PATHS.home[lang]} className="btn btn-glass">
                  {g.success.back}
                </Link>
              </div>
            ) : (
              <>
                <div className="waitlist-card-head">
                  <h2 className="waitlist-card-title">{g.cardTitle}</h2>
                  <p className="waitlist-card-sub">{g.cardSub}</p>
                </div>

                <form className="form" onSubmit={handleSubmit} noValidate>
                  {/* Honeypot field — hidden from people, tempting to bots. */}
                  <input
                    type="text"
                    name="botcheck"
                    value={form.botcheck}
                    onChange={handleChange}
                    className="hp-field"
                    tabIndex="-1"
                    autoComplete="off"
                    aria-hidden="true"
                  />

                  <div className="field">
                    <label htmlFor="name">{g.labels.name}</label>
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
                    <label htmlFor="email">{g.labels.email}</label>
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
                    <label htmlFor="phone">{g.labels.phone}</label>
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
                    <label htmlFor="business_name">{g.labels.business}</label>
                    <input
                      id="business_name"
                      name="business_name"
                      type="text"
                      value={form.business_name}
                      onChange={handleChange}
                      autoComplete="organization"
                      required
                      aria-invalid={errors.business_name ? 'true' : 'false'}
                      aria-describedby={
                        errors.business_name ? 'business_name-error' : undefined
                      }
                    />
                    {errors.business_name && (
                      <span className="field-error" id="business_name-error">
                        {errors.business_name}
                      </span>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-block"
                    disabled={status === 'submitting'}
                  >
                    {status === 'submitting' ? g.submitting : g.submit}
                    {status !== 'submitting' && <Icon name="arrow_forward" />}
                  </button>

                  <p className="form-note">{g.note}</p>

                  {/* Inline error — polite live region, no alert(), no reload. */}
                  <div className="form-status" role="status" aria-live="polite">
                    {status === 'error' && feedback && (
                      <p className="status-error">{feedback}</p>
                    )}
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
