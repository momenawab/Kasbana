# Kasbana — Frontend (Coming Soon)

Public website for **Kasbana** (Arabic wordmark: **كسبانة**), a digital
customer-loyalty platform. Bilingual: a full **English** site at `/` and a full
**Arabic (RTL)** site at `/ar`, with a language switcher in the header.

Built with **Vite + React** (JavaScript), `react-router-dom`, and
`react-helmet-async`. No backend server for the form — submissions are emailed
via [Web3Forms](https://web3forms.com).

> This is the **`frontend`** branch. See the branch map below.

---

## Branch map

| Branch        | Holds                          | Notes                                                       |
| ------------- | ------------------------------ | ----------------------------------------------------------- |
| `main`        | Docs / project overview        | Landing page for the repo.                                  |
| `frontend`    | This React app (source)        | Develop here.                                               |
| `Backend`     | Django project                 | API / business logic.                                       |
| `deployment`  | **Built** static site          | Hostinger serves this branch directly. Auto-built from CI.  |

**Deploy flow:** push to `frontend` → GitHub Action builds → publishes `dist/`
to `deployment` → Hostinger redeploys. (See `.github/workflows/deploy.yml`.)

---

## Routes

| English    | Arabic         | Page        |
| ---------- | -------------- | ----------- |
| `/`        | `/ar`          | Coming Soon |
| `/support` | `/ar/support`  | Support form |
| `/privacy` | `/ar/privacy`  | Privacy policy |

All copy lives in `src/i18n/index.js`. Each page renders in one language;
`<html lang/dir>` and the Cairo font switch automatically on the Arabic site.

---

## Quick start

```bash
npm install      # install dependencies
npm run dev      # dev server (http://localhost:5173)
npm run build    # production build → dist/
npm run preview  # preview the production build
```

> Requires Node 18+ (CI uses Node 20).

---

## ⚙️ Configuration (the only things you edit)

### 1. Web3Forms access key — required for the form to send

1. Create a **free** key at [web3forms.com](https://web3forms.com). The
   **destination email** is whatever you register there — that's where every
   submission lands.
2. In **`src/pages/Support.jsx`**, replace:

   ```js
   const WEB3FORMS_ACCESS_KEY = 'YOUR_WEB3FORMS_ACCESS_KEY'
   ```

   A commented **Formspree** alternative is in the same file.

### 2. Contact email & canonical domain — `src/config.js`

```js
export const CONTACT_EMAIL = 'contact@kasbana.net'  // shown on the site
export const SITE_URL = 'https://kasbana.net'        // OG / canonical / hreflang
```

---

## Deployment (Hostinger)

Hostinger is connected to the **`deployment`** branch and serves the built files
from the web root. SPA routing is handled by **`public/.htaccess`** (Apache
rewrite), which Vite copies into `dist/` on every build — so `/support`,
`/ar/privacy`, etc. resolve on refresh and direct links.

- **Automatic:** push to `frontend`; the Action publishes `dist/` to
  `deployment`. To disable, delete `.github/workflows/deploy.yml`.
- **Manual:** `npm run build`, then commit the contents of `dist/` to the
  `deployment` branch.

> `public/_redirects` (Netlify) and `vercel.json` (Vercel) are also included in
> case you ever host there; they're harmless on Hostinger.

---

## Project structure

```
src/
  main.jsx            # Router + HelmetProvider
  App.jsx             # EN routes ("/") + AR routes ("/ar")
  config.js           # ← contact email + canonical domain
  i18n/index.js       # ← all EN/AR copy + language context
  components/          # Layout, Header (lang switch), Footer, Seo
  pages/              # Home, Support, Privacy, NotFound
  styles/index.css
public/
  .htaccess           # Apache SPA rewrite (copied into dist/)
  _redirects          # Netlify SPA rewrite
  favicon.svg
```

---

## Notes

- **Accessibility:** labelled fields, `aria-invalid`/`aria-describedby`, a polite
  `role="status"` live region, visible focus rings, reduced-motion support.
- **i18n/SEO:** per-language `<title>`/description, canonical, and `hreflang`
  alternates (`en`, `ar`, `x-default`).
- **Spam protection:** hidden honeypot (`botcheck`) + required-field validation.
  No `alert()`, no page reloads.
