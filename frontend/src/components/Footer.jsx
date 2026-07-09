import { Link, useLocation } from 'react-router-dom'
import { BRAND_NAME, CONTACT_EMAIL } from '../config.js'
import { useLang, PAGE_PATHS, localizePath } from '../i18n/index.js'

export default function Footer() {
  const { lang, t } = useLang()
  const { pathname } = useLocation()
  const year = new Date().getFullYear()
  const p = (page) => PAGE_PATHS[page][lang]

  // Language switcher → equivalent page in the other language. Moved here from
  // the header so the top bar stays lean.
  const switchHref = localizePath(pathname, t.switchTo)

  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div className="footer-brand">
          <span className="footer-lockup">
            <img src="/logo.svg" alt="" className="footer-logo" />
            <span className="footer-name">{BRAND_NAME}</span>
          </span>
          <p className="footer-tagline">{t.footer.tagline}</p>
        </div>

        <nav className="footer-links" aria-label="Footer">
          <Link to={p('support')} className="footer-link">
            {t.nav.support}
          </Link>
          <Link to={p('privacy')} className="footer-link">
            {t.nav.privacy}
          </Link>
          <a className="footer-link" href={`mailto:${CONTACT_EMAIL}`}>
            {CONTACT_EMAIL}
          </a>
          <Link to={switchHref} className="footer-link lang-switch" hrefLang={t.switchTo}>
            {t.switchLabel}
          </Link>
        </nav>

        <p className="footer-copy">
          © {year} {BRAND_NAME}. {t.footer.rights}
        </p>
      </div>
    </footer>
  )
}
