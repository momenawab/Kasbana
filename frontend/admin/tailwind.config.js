/** @type {import('tailwindcss').Config} */
// Platform admin console — Stampn brand identity, dark back-office skin.
// Violet→fuchsia on a cool violet-tinted slate, matching the merchant
// dashboard's dark theme (frontend/dashboard index.css `.dark`). Dark-only:
// a dense operations console reads best on a dark canvas.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Violet-tinted slate surfaces (Stampn dark neutrals).
        bg: '#0F0D18', // app background (deep violet-black)
        surface: { DEFAULT: '#1E1B2E', 2: '#262238', 3: '#332F45' },
        line: '#2F2A42',
        // Brand — Stampn violet (primary / CTA) + fuchsia accent.
        brand: { DEFAULT: '#845AEA', d: '#6E42D6', bg: '#2D244A' },
        fuchsia: { DEFAULT: '#D43DCF', d: '#B82FB3', bg: '#3A2042' },
        tx: { DEFAULT: '#EDEBF5', 2: '#A9A3BE', 3: '#7C7891' },
        // Status — tuned to read on the dark violet canvas.
        success: '#4DB6A8',
        warn: '#E0A23B',
        danger: '#E5776B',
        info: '#6EA8F0',
        // Aliases for the Wallet Studio components copied from the merchant
        // dashboard (frontend/dashboard/src/components). Those files are shared
        // by sight with their originals, so mapping the dashboard's palette
        // names here keeps the copies textually identical to their source
        // instead of scattering hand-renamed classes through 1,600 lines — which
        // is what makes a later diff against the dashboard readable at all.
        violet: { DEFAULT: '#845AEA', d: '#6E42D6' }, // = brand
        teal: '#4DB6A8', // = success
        paper: '#262238', // = surface-2 (the inset well behind controls)
        slate: '#EDEBF5', // = tx (ink on a light chip)
      },
      fontFamily: {
        head: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: { card: '16px', ctl: '10px' },
      boxShadow: {
        card: '0 8px 24px -12px rgba(0,0,0,.5)',
        pop: '0 16px 48px -16px rgba(132,90,234,.45)',
      },
    },
  },
  plugins: [],
}
