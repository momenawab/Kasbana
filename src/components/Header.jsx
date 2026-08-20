import { Link, NavLink } from 'react-router-dom'
import { BRAND_NAME } from '../config.js'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

export default function Header() {
  const { lang, t } = useLang()

  const p = (page) => PAGE_PATHS[page][lang]

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to={p('home')} className="wordmark" aria-label={`${BRAND_NAME} home`}>
          <img src="/logo.svg" alt="" className="wordmark-logo" />
          <span className="wordmark-text">{BRAND_NAME}</span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          <NavLink to={p('home')} end className="nav-link">
            {t.nav.home}
          </NavLink>
          <NavLink to={p('pricing')} className="nav-link">
            {t.nav.pricing}
          </NavLink>
          <NavLink to={p('about')} className="nav-link">
            {t.nav.about}
          </NavLink>
          <NavLink to={p('contact')} className="nav-link">
            {t.nav.contact}
          </NavLink>
        </nav>

        <div className="header-right">
          {/*
            Log-in is intentionally NOT shown in the header — the Client
            Dashboard isn't enabled yet. The link still lives in the codebase
            (DASHBOARD_LOGIN_URL in config.js); re-add the <a> here to restore it.
            The language switcher now lives in the footer.
          */}

          {/* Get started → the lead form (name / email / phone / business). */}
          <Link to={p('getStarted')} className="btn btn-launch header-cta">
            {t.nav.getStarted}
          </Link>
        </div>
      </div>
    </header>
  )
}
