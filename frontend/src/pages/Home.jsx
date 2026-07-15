import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

// Material Symbols icon. Decorative by default — callers that convey meaning
// with an icon alone should pass a label instead.
function Icon({ name, className = '' }) {
  return (
    <span className={`ms ${className}`} aria-hidden="true">
      {name}
    </span>
  )
}

export default function Home() {
  const { lang, t } = useLang()
  const h = t.home
  const pv = h.preview
  const pb = h.pricingBand
  const fmt = (n) => n.toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-US')

  // Bento layout: large, small, small, large.
  const featureSpan = ['feature-lg', 'feature-sm', 'feature-sm', 'feature-lg']

  return (
    <>
      <Seo page="home" />

      {/* Hero */}
      <section className="hero">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />
        <div className="ambient-orb orb-cyan" aria-hidden="true" />

        <div className="container hero-grid">
          {/* Left: content */}
          <div className="hero-content">
            <span className="pill">
              <Icon name="stars" className="pill-icon" />
              {h.pill}
            </span>

            <h1 className="hero-title">
              {h.title} <span className="text-gradient">{h.titleAccent}</span>
            </h1>

            <p className="hero-lead">{h.lead}</p>

            <div className="hero-actions">
              <Link to={PAGE_PATHS.getStarted[lang]} className="btn btn-primary">
                {h.ctaPrimary}
                <Icon name="arrow_forward" />
              </Link>
              <Link to={PAGE_PATHS.support[lang]} className="btn btn-glass">
                <Icon name="play_circle" />
                {h.contactCta}
              </Link>
            </div>

            <div className="social-proof">
              <span className="proof-dots" aria-hidden="true">
                <span className="proof-dot" />
                <span className="proof-dot" />
                <span className="proof-dot" />
              </span>
              <span>{h.socialProof}</span>
            </div>
          </div>

          {/* Right: illustrative product preview (decorative) */}
          <div className="hero-visual" aria-hidden="true">
            <div className="visual-orb visual-orb-1" />
            <div className="visual-orb visual-orb-2" />
            <div className="visual-orb visual-orb-3" />

            <Icon name="loyalty" className="float-icon float-icon-1" />
            <Icon name="qr_code_2" className="float-icon float-icon-2" />
            <Icon name="card_giftcard" className="float-icon float-icon-3" />

            {/* Sample loyalty card */}
            <div className="wallet-card">
              <div className="wallet-card-top">
                <div>
                  <div className="wallet-card-tier">{pv.cardTier}</div>
                  <div className="wallet-card-name">{pv.cardName}</div>
                </div>
                <span className="wallet-card-logo ms">loyalty</span>
              </div>

              <div className="wallet-card-stamps-label">{pv.stampsLabel}</div>
              <div className="wallet-card-stamps">
                {Array.from({ length: 10 }).map((_, i) => (
                  <span
                    key={i}
                    className={`stamp ${i < 9 ? 'stamp-filled' : ''}`}
                  >
                    {i < 9 ? <span className="ms">check</span> : i + 1}
                  </span>
                ))}
              </div>

              <div className="wallet-card-qr">
                <span className="ms">qr_code_2</span>
                <span>{pv.stampsCount}</span>
              </div>
            </div>

            {/* Live preview badge */}
            <div className="glass-chip chip-live">
              <span className="live-dot" />
              <span>{pv.liveLabel}</span>
            </div>

            {/* Reward unlocked chip */}
            <div className="glass-chip chip-reward">
              <span className="chip-ic chip-ic-cyan ms">redeem</span>
              <div>
                <div className="chip-title">{pv.rewardUnlocked}</div>
                <div className="chip-sub">{pv.rewardItem}</div>
              </div>
            </div>

            {/* Activity chip */}
            <div className="glass-chip chip-activity">
              <span className="chip-ic chip-ic-purple ms">star</span>
              <div>
                <div className="chip-title">{pv.activityName}</div>
                <div className="chip-sub">{pv.activity}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What we're building — bento grid */}
      <section className="section">
        <div className="container">
          <div className="section-head">
            <h2 className="section-title">{h.sectionTitle}</h2>
            <p className="section-sub">{h.sectionSub}</p>
          </div>

          <div className="bento-grid">
            {h.features.map((f, i) => (
              <article
                className={`glass-panel feature-card ${featureSpan[i]}`}
                key={f.title}
              >
                <div className="feature-glow" aria-hidden="true" />
                <div className="feature-icon-wrapper">
                  <Icon name={f.icon} />
                </div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-body">{f.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing preview band — links to the full Pricing page */}
      <section className="section">
        <div className="container">
          <div className="section-head">
            <h2 className="section-title">{pb.title}</h2>
            <p className="section-sub">{pb.sub}</p>
          </div>

          <div className="pricing-grid">
            {t.pricing.plans.map((plan) => (
              <div
                key={plan.key}
                className={`glass-panel pricing-card ${plan.popular ? 'is-popular' : ''}`}
              >
                {plan.popular && <span className="pricing-ribbon">{pb.popular}</span>}
                <h3 className="pricing-name">{plan.name}</h3>
                <p className="pricing-tagline">{plan.tagline}</p>
                <div className="pricing-price">
                  {plan.custom ? (
                    <span className="pricing-amount pricing-amount-sm">{plan.priceLabel}</span>
                  ) : (
                    <>
                      <span className="pricing-amount">{fmt(plan.monthly)}</span>
                      <span className="pricing-unit">
                        {t.pricing.currency} {pb.perMonth}
                      </span>
                    </>
                  )}
                </div>
                <Link
                  to={plan.custom ? PAGE_PATHS.contact[lang] : PAGE_PATHS.getStarted[lang]}
                  className={`btn btn-block ${plan.popular ? 'btn-primary' : 'btn-glass'}`}
                >
                  {plan.custom ? t.pricing.contactCta : t.pricing.cta}
                </Link>
              </div>
            ))}
          </div>

          <p className="pricing-note center">
            <Link to={PAGE_PATHS.pricing[lang]} className="btn btn-glass">
              {pb.seeAll}
              <Icon name="arrow_forward" />
            </Link>
          </p>
        </div>
      </section>
    </>
  )
}
