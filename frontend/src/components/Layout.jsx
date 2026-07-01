import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Header from './Header.jsx'
import Footer from './Footer.jsx'
import { LangContext, translations } from '../i18n/index.js'

/**
 * Wraps every page for a given language: sets <html lang/dir>, provides the
 * translation context, and renders the shared Header/Footer around the route.
 */
export default function Layout({ lang }) {
  const t = translations[lang]

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = t.dir
  }, [lang, t.dir])

  return (
    <LangContext.Provider value={{ lang, t }}>
      <div className="app-shell">
        <Header />
        <main id="main" className="app-main">
          <Outlet />
        </main>
        <Footer />
      </div>
    </LangContext.Provider>
  )
}
