import { Helmet } from 'react-helmet-async'
import { SITE_URL } from '../config.js'
import { useLang, translations, PAGE_PATHS } from '../i18n/index.js'

/**
 * Per-route <head>: title, description, canonical, Open Graph, and hreflang
 * alternates pointing at the same page in the other language.
 *
 * @param {{ page: 'home' | 'support' | 'privacy' }} props
 */
export default function Seo({ page }) {
  const { lang, t } = useLang()
  const meta = t.seo[page]
  const url = `${SITE_URL}${PAGE_PATHS[page][lang]}`

  return (
    <Helmet>
      <html lang={lang} dir={t.dir} />
      <title>{meta.title}</title>
      <meta name="description" content={meta.description} />
      <link rel="canonical" href={url} />

      {/* Language alternates */}
      <link rel="alternate" hrefLang="en" href={`${SITE_URL}${PAGE_PATHS[page].en}`} />
      <link rel="alternate" hrefLang="ar" href={`${SITE_URL}${PAGE_PATHS[page].ar}`} />
      <link rel="alternate" hrefLang="x-default" href={`${SITE_URL}${PAGE_PATHS[page].en}`} />

      <meta property="og:type" content="website" />
      <meta property="og:site_name" content="Kasbana" />
      <meta property="og:locale" content={lang === 'ar' ? 'ar_EG' : 'en_US'} />
      <meta property="og:title" content={meta.title} />
      <meta property="og:description" content={meta.description} />
      <meta property="og:url" content={url} />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={meta.title} />
      <meta name="twitter:description" content={meta.description} />
    </Helmet>
  )
}

// Re-export so callers don't need a second import for the raw dictionary.
export { translations }
