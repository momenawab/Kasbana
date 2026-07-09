/** @type {import('tailwindcss').Config} */
// Brand tokens — derived from the Stampn logo (Group 2.svg):
// a violet→fuchsia stack of loyalty cards on a cool slate neutral.
//
// Neutrals (paper/surface/line/tx*) are CSS-variable backed so the whole app
// flips between light and dark themes without per-element `dark:` classes —
// the values live in index.css under :root and .dark. Brand hues
// (violet/fuchsia/slate/teal) stay fixed so they read the same in both themes.
function withVar(name) {
  return `rgb(var(${name}) / <alpha-value>)`
}

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Primary brand — violet (back card / CTA).
        violet: { DEFAULT: '#845AEA', d: '#6E42D6', bg: withVar('--violet-bg') },
        // Accent — fuchsia (middle card + check badge).
        fuchsia: { DEFAULT: '#D43DCF', d: '#B82FB3', bg: withVar('--fuchsia-bg') },
        // Neutral dark — cool, violet-tinted charcoal (front card, always-dark panels).
        slate: { DEFAULT: '#1E1B2E', 2: '#2E2A3B', 3: '#4A4658' },

        // Theme-aware neutrals (defined in index.css :root / .dark).
        paper: withVar('--paper'), // app canvas
        surface: { DEFAULT: withVar('--surface'), 2: withVar('--surface-2') }, // cards / panels
        line: withVar('--line'),
        tx: { DEFAULT: withVar('--tx'), 2: withVar('--tx-2'), 3: withVar('--tx-3') },

        // Success stays a cool teal-green; it reads fine beside violet.
        teal: { DEFAULT: '#1C7C73', bg: withVar('--teal-bg') },
        success: '#1C7C73',
        warn: '#C6862A',
        danger: '#C0392B',
      },
      fontFamily: {
        head: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        ar: ['Cairo', 'Tajawal', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: { card: '18px', ctl: '10px' },
      boxShadow: {
        // Soft, low-contrast card lift for light mode. In dark mode borders do
        // the separating work, so these shadows are barely visible (by design).
        card: '0 1px 2px rgba(30,27,46,.04), 0 8px 24px -12px rgba(30,27,46,.12)',
        bold: '0 12px 32px -10px rgba(30,27,46,.28)',
        pop: '0 16px 48px -16px rgba(132,90,234,.45)',
      },
    },
  },
  plugins: [],
}
