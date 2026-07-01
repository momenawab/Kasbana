import { useState } from 'react'
import Seo from '../components/Seo.jsx'
import { CONTACT_EMAIL } from '../config.js'
import { useLang } from '../i18n/index.js'

// ─────────────────────────────────────────────────────────────────────────────
// Web3Forms: sign up (free) at https://web3forms.com, paste your access key
// below. The destination email is the address you register there — that's where
// every submission from this form is delivered. No backend server required.
// ─────────────────────────────────────────────────────────────────────────────
const WEB3FORMS_ACCESS_KEY = 'YOUR_WEB3FORMS_ACCESS_KEY'

// ── Formspree alternative ────────────────────────────────────────────────────
// Prefer Formspree? Create a form at https://formspree.io to get an endpoint
// like https://formspree.io/f/abcdwxyz, then POST the same JSON body to it:
//
//   const FORMSPREE_ENDPOINT = 'https://formspree.io/f/YOUR_FORM_ID'
//   const res = await fetch(FORMSPREE_ENDPOINT, {
//     method: 'POST',
//     headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
//     body: JSON.stringify({ name, email, subject, message }),
//   })
// ─────────────────────────────────────────────────────────────────────────────

const EMPTY = { name: '', email: '', subject: '', message: '', botcheck: '' }

export default function Support() {
  const { t } = useLang()
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
      const res = await fetch('https://api.web3forms.com/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          access_key: WEB3FORMS_ACCESS_KEY,
          name: form.name,
          email: form.email,
          subject: form.subject,
          message: form.message,
          botcheck: form.botcheck,
          from_name: 'Stampn Support Form',
        }),
      })

      const data = await res.json()

      if (data.success) {
        setStatus('success')
        setFeedback(s.success)
        setForm(EMPTY)
      } else {
        setStatus('error')
        setFeedback(data.message || s.errors.generic)
      }
    } catch (err) {
      setStatus('error')
      setFeedback(s.errors.network)
    }
  }

  return (
    <>
      <Seo page="support" />

      <section className="section">
        <div className="container container-narrow">
          <h1 className="page-title">{s.title}</h1>
          <p className="page-lead">{s.lead}</p>
          <p className="page-meta">
            {s.meta} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>

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
                rows="6"
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
            </button>

            {/* Inline status — polite live region, no alert(), no reload. */}
            <div className="form-status" role="status" aria-live="polite">
              {status === 'success' && feedback && (
                <p className="status-success">{feedback}</p>
              )}
              {status === 'error' && feedback && (
                <p className="status-error">{feedback}</p>
              )}
            </div>
          </form>
        </div>
      </section>
    </>
  )
}
