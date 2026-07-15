import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

function Icon({ name, className = '' }) {
  return (
    <span className={`ms ${className}`} aria-hidden="true">
      {name}
    </span>
  )
}

export default function About() {
  const { lang, t } = useLang()
  const a = t.about

  return (
    <>
      <Seo page="about" />

      <section className="section">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-cyan" aria-hidden="true" />

        <div className="container container-narrow">
          <span className="pill">
            <Icon name="favorite" className="pill-icon" />
            {a.pill}
          </span>
          <h1 className="page-title">
            {a.title} <span className="text-gradient">{a.titleAccent}</span>
          </h1>
          <p className="page-lead">{a.lead}</p>

          {a.sections.map((s) => (
            <div key={s.h}>
              <h2 className="prose-h">{s.h}</h2>
              <p className="prose">{s.p}</p>
            </div>
          ))}

          <div className="glass-panel about-cta">
            <h2 className="about-cta-title">{a.ctaTitle}</h2>
            <p className="about-cta-body">{a.ctaBody}</p>
            <div className="about-cta-actions">
              <Link to={PAGE_PATHS.getStarted[lang]} className="btn btn-primary">
                {a.ctaPrimary}
              </Link>
              <Link to={PAGE_PATHS.contact[lang]} className="btn btn-glass">
                {a.ctaSecondary}
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
