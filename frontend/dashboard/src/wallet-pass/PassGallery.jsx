// PassGallery — a live catalogue of every template rendered from the registry's
// sample data. A theme switcher recolours all passes (or "Default" keeps each
// template's own theme) and a light/dark toggle reframes the page chrome, so the
// whole system can be reviewed at a glance. Cards are capped to a phone-like
// width and laid out responsively.
import { useState } from 'react'
import { GALLERY_CARDS } from './registry'
import { THEME_SWATCHES } from './components'

export default function PassGallery() {
  const [theme, setTheme] = useState(null) // null → each template's default
  const [dark, setDark] = useState(false)

  return (
    <div
      className={`min-h-screen px-6 py-8 transition-colors ${
        dark ? 'bg-[#0B1220] text-white' : 'bg-paper text-slate'
      }`}
    >
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-head text-2xl font-bold">Wallet Pass Templates</h1>
            <p className={`text-sm ${dark ? 'text-white/60' : 'text-tx-3'}`}>
              Eight Apple-Wallet-style templates, all prop-driven.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDark((d) => !d)}
            className={`rounded-ctl border px-3 py-1.5 text-sm font-semibold ${
              dark ? 'border-white/20' : 'border-line'
            }`}
          >
            {dark ? '☾ Dark' : '☀ Light'}
          </button>
        </div>

        {/* Theme switcher */}
        <div className="mb-8 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setTheme(null)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold ${
              theme === null
                ? 'border-violet bg-violet text-white'
                : dark
                  ? 'border-white/20'
                  : 'border-line'
            }`}
          >
            Default
          </button>
          {THEME_SWATCHES.map((sw) => (
            <button
              key={sw.key}
              type="button"
              onClick={() => setTheme(sw.key)}
              aria-label={sw.key}
              title={sw.key}
              style={{ background: sw.bg }}
              className={`h-7 w-7 rounded-full ring-2 ring-offset-2 ${
                theme === sw.key ? 'ring-violet' : 'ring-transparent'
              } ${dark ? 'ring-offset-[#0B1220]' : 'ring-offset-paper'}`}
            />
          ))}
        </div>

        <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-6">
          {GALLERY_CARDS.map(({ key, name, component: Pass, theme: def, sample }) => (
            <div key={key} className="flex flex-col items-center gap-3">
              <div className="w-full max-w-[280px]">
                <Pass {...sample} theme={theme || def} />
              </div>
              <span className={`text-xs font-semibold ${dark ? 'text-white/70' : 'text-tx-2'}`}>
                {name}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
