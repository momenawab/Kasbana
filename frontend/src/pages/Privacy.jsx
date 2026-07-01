import Seo from '../components/Seo.jsx'
import { CONTACT_EMAIL } from '../config.js'
import { useLang } from '../i18n/index.js'

export default function Privacy() {
  const { t } = useLang()
  const p = t.privacy

  return (
    <>
      <Seo page="privacy" />

      <section className="section">
        <div className="container container-narrow">
          <h1 className="page-title">{p.title}</h1>
          <p className="page-meta">{p.updated}</p>

          <p className="prose">{p.intro}</p>

          <h2 className="prose-h">{p.collectH}</h2>
          <p className="prose">{p.collectP}</p>
          <ul className="prose-list">
            {p.collectList.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="prose">{p.collectNote}</p>

          <h2 className="prose-h">{p.useH}</h2>
          <p className="prose">{p.useP}</p>

          <h2 className="prose-h">{p.keepH}</h2>
          <p className="prose">{p.keepP}</p>

          <h2 className="prose-h">{p.deleteH}</h2>
          <p className="prose">
            {p.deleteP1} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>{' '}
            {p.deleteP2}
          </p>

          <h2 className="prose-h">{p.contactH}</h2>
          <p className="prose">
            {p.contactP}{' '}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>
        </div>
      </section>
    </>
  )
}
