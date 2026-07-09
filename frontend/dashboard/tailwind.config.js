/** @type {import('tailwindcss').Config} */
// Brand tokens — derived from the Stampn logo (Group 2.svg):
// a violet→fuchsia stack of loyalty cards on a cool slate neutral.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Primary brand — violet (back card / CTA).
        violet: { DEFAULT: '#845AEA', d: '#6E42D6', bg: '#EFEAFC' },
        // Accent — fuchsia (middle card + check badge).
        fuchsia: { DEFAULT: '#D43DCF', d: '#B82FB3', bg: '#FBEAFA' },
        // Neutral dark — cool, violet-tinted charcoal (front card / text).
        slate: { DEFAULT: '#1E1B2E', 2: '#2E2A3B', 3: '#4A4658' },
        paper: '#F8F7FC',
        line: '#E9E6F2',
        tx: { DEFAULT: '#211F2B', 2: '#5B5766', 3: '#8B8798' },
        // Success stays a cool teal-green; it reads fine beside violet.
        teal: { DEFAULT: '#1C7C73', bg: '#E1F0EE' },
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
      borderRadius: { card: '16px', ctl: '10px' },
      boxShadow: { bold: '0 12px 32px -10px rgba(30,27,46,.28)' },
    },
  },
  plugins: [],
}
