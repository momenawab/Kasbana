import { useState } from 'react'
import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { CONTACT_EMAIL, CONTACT_ENDPOINT } from '../config.js'
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
// The contact form POSTs to our own backend (/api/v1/contact). Messages land in
// the admin console (Messages section). No third-party form service.
// ─────────────────────────────────────────────────────────────────────────────

const EMPTY = { name: '', email: '', subject: '', message: '', botcheck: '' }

export default function Support() {
  const { lang, t } = useLang()
  const s = t.support

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
    if (!form.name.trim()) next.name = s.errors.name
    if (!form.email.trim()) {
      next.email = s.errors.email
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = s.errors.emailInvalid
    }
    if (!form.subject.trim()) next.subject = s.errors.subject
    if (!form.message.trim()) next.message = s.errors.message
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
      setFeedback(s.errors.fix)
      return
    }

    setStatus('submitting')

    try {
      const res = await fetch(CONTACT_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          subject: form.subject,
          message: form.message,
          botcheck: form.botcheck,
        }),
      })

      if (res.ok) {
        setStatus('success')
        setForm(EMPTY)
      } else {
        setStatus('error')
        setFeedback(s.errors.generic)
      }
    } catch (err) {
      setStatus('error')
      setFeedback(s.errors.network)
    }
  }

  return (
    <>
      <Seo page="support" />

      <section className="waitlist">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />
        <div className="ambient-orb orb-cyan" aria-hidden="true" />

        <div className="container waitlist-grid">
          {/* Left: the pitch */}
          <div className="waitlist-pitch">
            <span className="pill">
              <Icon name="chat_bubble" className="pill-icon" />
              {s.pill}
            </span>

            <h1 className="waitlist-title">
              {s.title} <span className="text-gradient">{s.titleAccent}</span>
            </h1>

            <p className="waitlist-lead">{s.lead}</p>

            <ul className="waitlist-benefits">
              {s.points.map((pt) => (
                <li className="waitlist-benefit" key={pt.text}>
                  <Icon name={pt.icon} />
                  <span>{pt.text}</span>
                </li>
              ))}
            </ul>

            <p className="waitlist-email">
              {s.emailLabel}{' '}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
            </p>
          </div>

          {/* Right: the contact card (form → confirmation on success) */}
          <div className="glass-panel waitlist-card">
            {status === 'success' ? (
              <div className="waitlist-success" role="status" aria-live="polite">
                <div className="success-badge">
                  <Icon name="check" />
                </div>
                <h2 className="success-title">{s.success.title}</h2>
                <p className="success-body">{s.success.body}</p>
                <p className="success-note">{s.success.note}</p>
                <Link to={PAGE_PATHS.home[lang]} className="btn btn-glass">
                  {s.success.back}
                </Link>
              </div>
            ) : (
              <>
                <div className="waitlist-card-head">
                  <h2 className="waitlist-card-title">{s.cardTitle}</h2>
                  <p className="waitlist-card-sub">{s.cardSub}</p>
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
                    <label htmlFor="name">{s.labels.name}</label>
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
                    <label htmlFor="email">{s.labels.email}</label>
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
                    <label htmlFor="subject">{s.labels.subject}</label>
                    <input
                      id="subject"
                      name="subject"
                      type="text"
                      value={form.subject}
                      onChange={handleChange}
                      required
                      aria-invalid={errors.subject ? 'true' : 'false'}
                      aria-describedby={errors.subject ? 'subject-error' : undefined}
                    />
                    {errors.subject && (
                      <span className="field-error" id="subject-error">
                        {errors.subject}
                      </span>
                    )}
                  </div>

                  <div className="field">
                    <label htmlFor="message">{s.labels.message}</label>
                    <textarea
                      id="message"
                      name="message"
                      rows="5"
                      value={form.message}
                      onChange={handleChange}
                      required
                      aria-invalid={errors.message ? 'true' : 'false'}
                      aria-describedby={errors.message ? 'message-error' : undefined}
                    />
                    {errors.message && (
                      <span className="field-error" id="message-error">
                        {errors.message}
                      </span>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary btn-block"
                    disabled={status === 'submitting'}
                  >
                    {status === 'submitting' ? s.submitting : s.submit}
                    {status !== 'submitting' && <Icon name="send" />}
                  </button>

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
