import { useState } from 'react'
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

export default function Pricing() {
  const { lang, t } = useLang()
  const p = t.pricing
  const [annual, setAnnual] = useState(false)

  const fmt = (n) => n.toLocaleString(lang === 'ar' ? 'ar-EG' : 'en-US')
  const contact = PAGE_PATHS.contact[lang]
  // A plan card sends the visitor to checkout with the plan + current billing
  // period; "Custom" still routes to contact sales.
  const checkoutTo = (plan) =>
    `${PAGE_PATHS.checkout[lang]}?plan=${plan.key}&billing=${annual ? 'annual' : 'monthly'}`

  return (
    <>
      <Seo page="pricing" />

      <section className="section">
        <div className="hero-aurora" aria-hidden="true" />
        <div className="ambient-orb orb-purple" aria-hidden="true" />

        <div className="container">
          <div className="section-head">
            <span className="pill">
              <Icon name="sell" className="pill-icon" />
              {p.pill}
            </span>
            <h1 className="page-title">
              {p.title} <span className="text-gradient">{p.titleAccent}</span>
            </h1>
            <p className="section-sub">{p.lead}</p>

            {/* Monthly / Annual toggle */}
            <div className="billing-toggle" role="group" aria-label={p.monthly + ' / ' + p.annual}>
              <button
                type="button"
                className={`billing-opt ${!annual ? 'is-active' : ''}`}
                onClick={() => setAnnual(false)}
                aria-pressed={!annual}
              >
                {p.monthly}
              </button>
              <button
                type="button"
                className={`billing-opt ${annual ? 'is-active' : ''}`}
                onClick={() => setAnnual(true)}
                aria-pressed={annual}
              >
                {p.annual}
                <span className="billing-save">{p.annualNote}</span>
              </button>
            </div>
          </div>

          <div className="pricing-grid">
            {p.plans.map((plan) => (
              <div
                key={plan.key}
                className={`glass-panel pricing-card ${plan.popular ? 'is-popular' : ''}`}
              >
                {plan.popular && <span className="pricing-ribbon">{p.popular}</span>}

                <h2 className="pricing-name">{plan.name}</h2>
                <p className="pricing-tagline">{plan.tagline}</p>

                <div className="pricing-price">
                  {plan.custom ? (
                    <span className="pricing-amount pricing-amount-sm">{plan.priceLabel}</span>
                  ) : (
                    <>
                      <span className="pricing-amount">
                        {fmt(annual ? plan.annual : plan.monthly)}
                      </span>
                      <span className="pricing-unit">
                        {p.currency} {annual ? p.perYear : p.perMonth}
                      </span>
                    </>
                  )}
                </div>
                {!plan.custom && annual && (
                  <p className="pricing-subprice">{p.billedAnnually}</p>
                )}

                <Link
                  to={plan.custom ? contact : checkoutTo(plan)}
                  className={`btn btn-block ${plan.popular ? 'btn-primary' : 'btn-glass'}`}
                >
                  {plan.custom ? p.contactCta : p.cta}
                </Link>

                <ul className="pricing-features">
                  {plan.features.map((f) => (
                    <li key={f}>
                      <Icon name="check" className="pricing-check" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <p className="pricing-note center">
            <Icon name="verified" /> {p.trialNote}
          </p>
        </div>
      </section>
    </>
  )
}
