import { Link } from 'react-router-dom'
import { BRAND_NAME, BRAND_NAME_AR, CONTACT_EMAIL } from '../config.js'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

export default function Footer() {
  const { lang, t } = useLang()
  const year = new Date().getFullYear()
  const p = (page) => PAGE_PATHS[page][lang]

  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div className="footer-brand">
          <span className="footer-name">{BRAND_NAME}</span>
          <span className="footer-name-ar" dir="rtl" lang="ar">
            {BRAND_NAME_AR}
          </span>
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
        </nav>

        <p className="footer-copy">
          © {year} {BRAND_NAME}. {t.footer.rights}
        </p>
      </div>
    </footer>
  )
}
