import { Link } from 'react-router-dom'
import Seo from '../components/Seo.jsx'
import { useLang, PAGE_PATHS } from '../i18n/index.js'

export default function NotFound() {
  const { lang, t } = useLang()
  const n = t.notFound

  return (
    <>
      <Seo page="home" />
      <section className="section">
        <div className="container container-narrow center">
          <h1 className="page-title">{n.title}</h1>
          <p className="page-lead">{n.lead}</p>
          <Link to={PAGE_PATHS.home[lang]} className="btn btn-primary">
            {n.cta}
          </Link>
        </div>
      </section>
    </>
  )
}
