import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

export default function Home() {
  const { lang, t } = useLang()
  const h = t.home

  return (
    <>
      <Seo page="home" />

      {/* Hero */}
      <section className="hero">
        <div className="hero-glow" aria-hidden="true" />
        <div className="container hero-inner">
          <span className="pill">{h.pill}</span>

          <h1 className="hero-title">{h.title}</h1>

          <p className="hero-lead">{h.lead}</p>

          <div className="hero-actions">
            <Link to={PAGE_PATHS.support[lang]} className="btn btn-primary">
              {h.contactCta}
            </Link>
            <Link to={PAGE_PATHS.privacy[lang]} className="btn btn-ghost">
              {h.privacyCta}
            </Link>
          </div>

          {/* Decorative amber ring / seal motif */}
          <div className="seal" aria-hidden="true">
            <span className="seal-ring seal-ring-1" />
            <span className="seal-ring seal-ring-2" />
            <span className="seal-star" />
          </div>
        </div>
      </section>

      {/* What we're building */}
      <section className="section">
        <div className="container">
          <h2 className="section-title">{h.sectionTitle}</h2>
          <p className="section-sub">{h.sectionSub}</p>

          <div className="feature-grid">
            {h.features.map((f) => (
              <article className="feature-card" key={f.title}>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-body">{f.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
