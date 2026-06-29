import { Link, NavLink, useLocation } from 'react-router-dom'
import { BRAND_NAME, BRAND_NAME_AR, DASHBOARD_LOGIN_URL, DASHBOARD_SIGNUP_URL } from '../config.js'
import { useLang, localizePath, PAGE_PATHS } from '../i18n/index.js'

export default function Header() {
  const { lang, t } = useLang()
  const { pathname } = useLocation()

  const switchHref = localizePath(pathname, t.switchTo)
  const p = (page) => PAGE_PATHS[page][lang]

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to={p('home')} className="wordmark" aria-label={`${BRAND_NAME} home`}>
          <span className="wordmark-latin">{BRAND_NAME}</span>
          <span className="wordmark-ar" dir="rtl" lang="ar">
            {BRAND_NAME_AR}
          </span>
        </Link>

        <div className="header-right">
          <nav className="site-nav" aria-label="Primary">
            <NavLink to={p('home')} end className="nav-link">
              {t.nav.home}
            </NavLink>
            <NavLink to={p('support')} className="nav-link">
              {t.nav.support}
            </NavLink>
            <NavLink to={p('privacy')} className="nav-link">
              {t.nav.privacy}
            </NavLink>
          </nav>

          {/* Language switcher → equivalent page in the other language */}
          <Link to={switchHref} className="lang-switch" hrefLang={t.switchTo}>
            {t.switchLabel}
          </Link>

          {/* Auth entry points → the Client Dashboard (separate subdomain) */}
          <a href={DASHBOARD_LOGIN_URL} className="nav-link header-login">
            {t.nav.login}
          </a>
          <a href={DASHBOARD_SIGNUP_URL} className="btn btn-primary header-cta">
            {t.nav.getStarted}
          </a>
        </div>
      </div>
    </header>
  )
}
