import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import {
  CONTACT_EMAIL,
  CONTACT_PHONE,
  CONTACT_PHONE_DISPLAY,
  BUSINESS_ADDRESS,
  BUSINESS_ADDRESS_AR,
} from '../config.js'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

function Icon({ name, className = '' }) {
  return (
    <span className={`ms ${className}`} aria-hidden="true">
      {name}
    </span>
  )
}

export default function Contact() {
  const { lang, t } = useLang()
  const c = t.contact
  const address = lang === 'ar' ? BUSINESS_ADDRESS_AR : BUSINESS_ADDRESS

  const methods = [
    {
      icon: 'mail',
      h: c.emailH,
      value: CONTACT_EMAIL,
      href: `mailto:${CONTACT_EMAIL}`,
      sub: c.emailSub,
      dir: 'ltr',
    },
    {
      icon: 'call',
      h: c.phoneH,
      value: CONTACT_PHONE_DISPLAY,
      href: `tel:${CONTACT_PHONE}`,
      sub: c.phoneSub,
      dir: 'ltr',
    },
    {
      icon: 'location_on',
      h: c.addressH,
      value: address,
      sub: c.addressSub,
    },
  ]

  return (
    <>
      <Seo page="contact" />

      <section className="section">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />

        <div className="container container-narrow">
          <div className="section-head">
            <span className="pill">
              <Icon name="alternate_email" className="pill-icon" />
              {c.pill}
            </span>
            <h1 className="page-title">
              {c.title} <span className="text-gradient">{c.titleAccent}</span>
            </h1>
            <p className="section-sub">{c.lead}</p>
          </div>

          <div className="contact-grid">
            {methods.map((m) => (
              <div key={m.h} className="glass-panel contact-card">
                <div className="contact-icon">
                  <Icon name={m.icon} />
                </div>
                <h2 className="contact-h">{m.h}</h2>
                {m.href ? (
                  <a className="contact-value" href={m.href} dir={m.dir}>
                    {m.value}
                  </a>
                ) : (
                  <span className="contact-value" dir={m.dir}>
                    {m.value}
                  </span>
                )}
                <p className="contact-sub">{m.sub}</p>
              </div>
            ))}
          </div>

          <div className="glass-panel contact-form-cta">
            <div>
              <h2 className="contact-h">{c.formH}</h2>
              <p className="contact-sub">{c.formP}</p>
            </div>
            <Link to={PAGE_PATHS.support[lang]} className="btn btn-glass">
              {c.formCta}
              <Icon name="arrow_forward" />
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
