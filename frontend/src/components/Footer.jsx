import { Link, useLocation } from 'react-router-dom'
import { BRAND_NAME, CONTACT_EMAIL, CONTACT_PHONE, CONTACT_PHONE_DISPLAY } from '../config.js'
import { useLang, PAGE_PATHS, localizePath } from '../i18n/index.js'

export default function Footer() {
  const { lang, t } = useLang()
  const { pathname } = useLocation()
  const year = new Date().getFullYear()
  const p = (page) => PAGE_PATHS[page][lang]
  const f = t.footer

  // Language switcher → equivalent page in the other language.
  const switchHref = localizePath(pathname, t.switchTo)

  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div className="footer-brand">
          <span className="footer-lockup">
            <img src="/logo.svg" alt="" className="footer-logo" />
            <span className="footer-name">{BRAND_NAME}</span>
          </span>
          <p className="footer-tagline">{f.tagline}</p>
          <a className="footer-contact" href={`mailto:${CONTACT_EMAIL}`}>
            {CONTACT_EMAIL}
          </a>
          <a className="footer-contact" href={`tel:${CONTACT_PHONE}`} dir="ltr">
            {CONTACT_PHONE_DISPLAY}
          </a>
        </div>

        <nav className="footer-cols" aria-label="Footer">
          <div className="footer-col">
            <h3 className="footer-col-h">{f.productH}</h3>
            <Link to={p('pricing')} className="footer-link">
              {f.pricing}
            </Link>
            <Link to={p('support')} className="footer-link">
              {f.support}
            </Link>
          </div>

          <div className="footer-col">
            <h3 className="footer-col-h">{f.companyH}</h3>
            <Link to={p('about')} className="footer-link">
              {f.about}
            </Link>
            <Link to={p('contact')} className="footer-link">
              {f.contact}
            </Link>
          </div>

          <div className="footer-col">
            <h3 className="footer-col-h">{f.legalH}</h3>
            <Link to={p('privacy')} className="footer-link">
              {f.privacy}
            </Link>
            <Link to={p('refund')} className="footer-link">
              {f.refund}
            </Link>
          </div>
        </nav>

        <div className="footer-bottom">
          <p className="footer-copy">
            © {year} {BRAND_NAME}. {f.rights}
          </p>
          <Link to={switchHref} className="footer-link lang-switch" hrefLang={t.switchTo}>
            {t.switchLabel}
          </Link>
        </div>
      </div>
    </footer>
  )
}
