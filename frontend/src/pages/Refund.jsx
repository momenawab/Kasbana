import Seo from '../components/Seo.jsx'
import { CONTACT_EMAIL } from '../config.js'
import { useLang } from '../i18n/index.js'

export default function Refund() {
  const { t } = useLang()
  const r = t.refund

  return (
    <>
      <Seo page="refund" />

      <section className="section">
        <div className="container container-narrow">
          <h1 className="page-title">{r.title}</h1>
          <p className="page-meta">{r.updated}</p>

          <p className="prose">{r.intro}</p>

          <h2 className="prose-h">{r.noRefundH}</h2>
          <p className="prose">{r.noRefundP}</p>

          <h2 className="prose-h">{r.cancelH}</h2>
          <p className="prose">{r.cancelP}</p>

          <h2 className="prose-h">{r.afterH}</h2>
          <p className="prose">{r.afterP}</p>

          <h2 className="prose-h">{r.trialH}</h2>
          <p className="prose">{r.trialP}</p>

          <h2 className="prose-h">{r.howH}</h2>
          <p className="prose">
            {r.howP} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </p>

          <h2 className="prose-h">{r.contactH}</h2>
          <p className="prose">
            {r.contactP} <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>
        </div>
      </section>
    </>
  )
}
